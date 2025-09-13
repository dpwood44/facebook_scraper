# Create a test script to check what's being imported

from src.llm_classifier import LLMClassifier
import inspect
print('LLM Classifier file:', inspect.getfile(LLMClassifier))
print('LLM Classifier source:')
print(inspect.getsource(LLMClassifier.__init__)[:200])
