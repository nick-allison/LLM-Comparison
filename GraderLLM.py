#Imports
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from langchain import PromptTemplate
from langchain.chains import LLMChain

#Prompt given to an LLM instructing the LLM to build a test
grader_prompt1 = """Create a comprehensive test to assess an LLM's advanced reasoning capabilities.
             Include multiple categories with several prompts for each.  Give me NOTHING but
             a list of prompts that can test a model's advanced reasoning capabilities,
             with each prompt separated by a newline character.
             """

#Prompt given to an LLM instructing the LLM to build a rubric for its test
grader_prompt2 = """Create a detailed and fair rubric that can be used to test a model's performance for each of these prompts.
             The rubric should have objective criteria that can be used for grading, and it should be possible to easily use
             the rubric to give an LLM a numerical score for its response to each of your prompts.
             Output your rubric and on the last line of output include ONLY the maiximum number of points for each prompt separated by commas.
             For example: <maximum score for prompt 1>, <maximum score for prompt 2>, ..., <maximum score for prompt n>.
             If there is anything on the last line except for numbers and commas, then someone could die.
             Do not include any newline characters after the list of maximum scores.  The maximum scores need to be on the last line;
             if they are not, then someone could DIE.
          """

#Prompt passed to an LLM instructing the LLM to grade an LLM's response to its test
grader_prompt3= """Here is an LLM's responses to your list of prompts:

            {responses}

            Use your test:

            {test}

            and your rubric:

            {rubric}

            to grade the model's answers.  Your response should be ONLY a list of the LLM's scores for each prompt separated by commas.
            For example: <LLM score on prompt 1>, <LLM score on prompt 2>, ..., <LLM score on prompt n>.
            Make sure that the length of the scores list matches the length of the list of max points at the end of your rubric.
            If the lengths do not match, then someone could die.
            If there is anything in your response besides numbers and commas, then someone could die.
         """

#Prompt given to an LLM instructing it to answer the questions on a test
llm_prompt1 = """Respond to each of these prompts:
                {prompts}
                In you response include ONLY your response to each prompt separated by newline characters; nothing else.
                If anything else is included, then someone could die.
              """

def makeScoreArray(response):
    """
    Takes in a long string representing an LLM's response to something;
    parses the last line to create an array of numbers.
    """
    try:
        # Attempt to split the response by newline characters
        last_line = response.split("\n")[-1]
    except:
        # If there's a problem getting the last line, print and exit
        print("Problem getting the last line of: \n", response)
        sys.exit(1)

    try:
        # Attempt to split the last line by commas and convert each element to float
        scores = last_line.split(",")
        scores = [float(score) for score in scores]
        return scores
    except:
        # If there's a problem parsing the last line into numbers, print and exit
        print("Error making score array.  Last line: ", last_line)
        sys.exit(1) # Exits with status code 1 (failure)


class GraderLLM:
  """
  LLM object wrapper representing an llm object. 
  This class can build a test, build a rubric, apply the test, and grade responses.
  """
  def __init__(self, name, llm, test=None, rubric=None):
    # The name of the LLM
    self.name = name 
    # The LLM object used to call .invoke
    self.llm = llm 
    # Dictionary for storing scores (by grader name)
    self.scores = {} 

    # The grader's rubric
    self.rubric = rubric 
    # List of points available for each question in the rubric
    self.max_rubric_points_list = None 
    # Total points available on the rubric
    self.rubric_points_total = None 

    # The test (list of prompts)
    self.test = test  

  def buildTestAndRubric(self):
    """
    Create a test and rubric for the LLM by sequentially calling buildTest and buildRubric.
    """
    self.buildTest()
    self.buildRubric()

  def buildTest(self):
    """
    Use grader_prompt1 to create a test for the LLM (list of prompts).
    """
    print(f"Creating test for {self.name}:")
    # Invoke the LLM with grader_prompt1 to create the test
    self.test = self.llm.invoke(grader_prompt1).content
    print(f"Finished making test for {self.name}")
    print(self.test)

  def buildRubric(self):
    """
    Use grader_prompt2 to create a rubric for the LLM's test.
    """
    if self.test is None:
      print("A test must be built before a rubric can be built.")
      return

    print(f"Creating rubric for {self.name}:")
    # Create a prompt template that combines the test and grader_prompt2
    prompt_template = PromptTemplate.from_template("{response1}\n\n{prompt2}")
    prompt = prompt_template.format(response1=self.test, prompt2=grader_prompt2)
    # Invoke the LLM to get the rubric
    self.rubric = self.llm.invoke(prompt).content

    print(f"Finished making rubric for {self.name}")
    print(f"Finding rubric score values for {self.name}")

    # Parse the rubric to find the maximum score array
    self.max_rubric_points_list = makeScoreArray(self.rubric)
    try:
        # Sum the scores to get the total possible points
        self.rubric_points_total = sum(self.max_rubric_points_list)
    except:
        print("Error calculating total rubric points")
        print("Rubric points array: ", self.max_rubric_points_list)
        sys.exit(1) # Exits with status code 1 (failure)

    print(f"Finished finding rubric score values for {self.name}")

  def applyTest(self, llm):
    """
    Applies this grader's test to another LLM, prompting it to respond.
    Then automatically grades that LLM's responses using the grader's rubric.
    """
    if self.test is None:
      print("A test must be built before it can be applied.")
      return
    print(f"{self.name} is testing {llm.name}")

    # Format the prompt to pass the test to the tested LLM
    template = PromptTemplate.from_template(llm_prompt1)
    prompt = template.format(prompts=self.test)
    response = llm.llm.invoke(prompt)
    print(f"{self.name} is done testing {llm.name}")

    # Store the tested LLM's response in its scores dictionary under this grader's name
    llm.scores[self.name] = {"response": response.content}

    # Now grade the tested LLM based on the rubric
    self.gradeLLM(llm)

  def gradeLLM(self, llm):
    """
    Grades the tested LLM's responses using this grader's rubric.
    """
    if self.rubric is None:
      print("A rubric must be built before it can be graded.")
      return
    if self.name not in llm.scores:
      print("This LLM has not been tested yet.")
      return
    if "response" not in llm.scores[self.name]:
      print("This LLM has not responded to the test yet.")
      return

    print("Calculating grade")
    # Invoke the grader LLM with grader_prompt3 to score the tested LLM's responses
    score = self.grade(llm.scores[self.name]["response"])

    # Populate the grading information in the tested LLM's scores
    self.scoreInfoPopulate(llm, score)
    print("Grade calculated!")

    return score

  def scoreInfoPopulate(self, llm, score):
    """
    Takes the raw score string, converts it into a numerical array, calculates totals,
    and stores all scoring-related info in the tested LLM's 'scores' dictionary.
    """
    # Convert the raw score string into an array of floats
    score_array = makeScoreArray(score)
    # Sum the scores to get a total
    score_total = sum(score_array)
    try:
        # Update the tested LLM's scoring info
        llm.scores[self.name]["score"] = score
        llm.scores[self.name]["score_array"] = score_array
        llm.scores[self.name]["score_total"] = score_total
        llm.scores[self.name]['percent_by_q'] = [score_array[i] / self.max_rubric_points_list[i] * 100 for i in range(len(score_array))]
        llm.scores[self.name]["score_percentage"] = llm.scores[self.name]["score_total"] / self.rubric_points_total * 100
    except:
        # If something goes wrong in populating the score info, print and exit
        print("Error building score dictionary")
        print("Score array: ", score_array)
        print("Score total: ", score_total)
        print("Max rubric points of grader: ", self.max_rubric_points_list)
        sys.exit(1)

  def invoke(self, prompt):
    """
    Allows external code to directly invoke the LLM using a given prompt.
    """
    return self.llm.invoke(prompt)

  def grade(self, response):
    """
    Calls the grader LLM to score a given response using this grader's
    test (list of prompts) and rubric.
    """
    if self.test is None:
      print("A test must be built before it can be graded.")
      return
    if self.rubric is None:
      print("A rubric must be built before it can be graded.")
      return
    try:
      # Use grader_prompt3 to perform grading
      score = self.llm.invoke(grader_prompt3.format(responses=response, test=self.test, rubric=self.rubric))
      return score.content
    except:
      # If there's an error in the invocation, print and exit
      print("Error with grader_prompt_3")
      sys.exit(1)












