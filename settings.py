import os
from os.path import join, dirname
from dotenv import load_dotenv

load_dotenv(verbose=True)

dotenv_path = join(dirname(__file__), ".env.prod")
load_dotenv(dotenv_path)

RAW_PATH = os.environ.get("RAW_PATH")
INPUT_PATH = os.environ.get("INPUT_PATH")
RESULT_PATH = os.environ.get("RESULT_PATH")
PRIORITY_DATA_PATH = os.environ.get("PRIORITY_DATA_PATH")

file_manager_config = {
    "raw_path": RAW_PATH,
    "input_path": INPUT_PATH,
    "result_path": RESULT_PATH,
    "priority_data_path": PRIORITY_DATA_PATH,
}
