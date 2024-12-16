# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
#     "pandas",
#      "python-dotenv",
#      "chardet",
#      "scikit-learn",
#      "matplotlib",
#      "seaborn"
# ]
# ///

import requests
import os
import pandas as pd
import sys
import chardet
from dotenv import load_dotenv
import itertools
import json
import io
import traceback


data = dict()

load_dotenv()
AIPROXY_TOKEN = os.getenv("AIPROXY_TOKEN")

url ="https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
model="gpt-4o-mini"
headers={"Content-Type":"application/json", "Authorization":f"Bearer {AIPROXY_TOKEN}"}

with open(sys.argv[1], 'rb') as f:
    result = chardet.detect(f.read())

df = pd.read_csv(sys.argv[1], encoding=result['encoding'])
df = df.dropna() 

numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns
column_combinations = itertools.combinations(numeric_columns, 2)

max_corr = -1  
second_max_corr = -1
max_corr_pair = None
second_max_corr_pair = None

for col1, col2 in column_combinations:
    correlation = df[[col1, col2]].corr().iloc[0, 1]  
    if correlation > max_corr :
        max_corr = correlation
        max_corr_pair = (col1, col2)
        data[col1] = json.loads(df.describe()[col1].to_json())
        data[col2] = json.loads(df.describe()[col2].to_json())
        
    
    if (correlation > second_max_corr and correlation < max_corr) : 
        second_max_corr_pair = (col1, col2)
        data[col1] = json.loads(df.describe()[col1].to_json())
        data[col2] = json.loads(df.describe()[col2].to_json())

content = (
    f"The name of file is {sys.argv[1]}."
    f"The columns it has are {df.columns}."
    "Consider the name of the column as key and its column summary as value of the dictionary passed. Can it be predicted why these have high correlation?"
    "If the columns with top 2 correlation doesn't have any column in common, why is it so?"
    "If any column is common then can that column be the column having output values?"
)


functions = [
    {
        "name":"correlation",
        "description":"Identifies if columns which have top 2 correlation contains similar column",
        "parameters":{
            "type":"object",
            "properties":{
                "is_columns_common":{
                    "type":"boolean",
                    "description":"it is a booelean that represents if column in top 2 correlations are similar"
                },
                "reason":{
                    "type":"string",
                    "description":"give reason in case they don't have any common columns or in case if they have"
                }
            },
            "required":["is_columns_common", "reason"]
        }
    }
]

josn_data= {
    "model":model,
    "messages":[
        {
            "role":"system", "content":content
        },
        {
            "role":"system", "content":json.dumps(data)
        }
    ],
    "functions":functions,
    "function_call":{"name":"correlation"}
}


r = requests.post(url=url, headers=headers, json=josn_data)

folder_name = os.path.splitext(sys.argv[1])[0]
print(folder_name)

instrctions = (
                "Generate python code to follow a sequence in the below manner:"
                f"First create a folder in the current directory named {folder_name} without the extension and just the name."
                "Then using the summaries provided for their respective column names, generate the python code without any comment to create an appropriate chart.Use the keys as the column names and values as the column summary and decide what can be an appropriate chart."
                "Then create a README.md file having the story about the analysis based on data, insights and implications of your findings."
                f"Make the code to export the chart as png.Keep images small. 512x512 px images are ideal. Export the chart and README.md to the created {sys.argv[1]} folder."
                "Remove any backslash which is not required to avoid unexpected character after line continuation character error "
              )

functions = [
    {
        "name":"generate_appropriate_chart_and_readme",
        "description":"Generates python code without comments to craete chart of the columns having high correlations and also the story about the analysis outcomes.",
        "parameters":{
            "type":"object",
            "properties":{
                "python_code":{
                    "type":"string",
                    "description":"Code to create the folder, charts for the column based on their summaries and also story about the analysis in README.md file"
                },
                "folder":{
                    "contents": [
                        { "type": "file", "name": "*.png" },
                        { "type": "file", "name": "TREADME.md" },
                    ]
                },
                "chart_name":{
                    "type":"string",
                    "description":"file name of the png chart"
                },
                "readme_file_summary":{
                    "type":"string",
                    "description":"a readme file named REAME.md having implications of findings"
                }
            },
            "required":['folder','python_code', 'chart_name', 'readme_file_summary']
        }
    }
]

josn_data= {
    "model":model,
    "messages":[
        {
            "role":"system", "content":instrctions
        },
        {
            "role":"system", "content":json.dumps(data)
        }
    ],
    "functions": functions,
    "function_call":{"name":"generate_appropriate_chart_and_readme"}
}

correction_instrctions = (
                            "I have send you the code generated and the error I am getting with the code."
                            "Assess the error and inprove the code to remove the errors"
)

def resend_request(code, error):
    correction_data = code + "\n" + error
    json_data = {
        "model":model,
        "messages":[
            {
                "role":"system", "content":instrctions
            },
            {
                "role":"user", "content":correction_data
            }
        ],
        "functions": functions,
        "function_call":{"name":"generate_appropriate_chart_and_readme"}
    }
    r = requests.post(url=url, headers=headers, json=josn_data)
    return r

limit=0
flag=True

r = requests.post(url=url, headers=headers, json=josn_data)
code_list=[]
error_list=[]

while flag and limit<3:
    try:
        if limit>=1:
            r=resend_request(code=code, error=error)
        print(r.json()['monthlyCost'])
        code = exec(json.loads(r.json()['choices'][0]['message']['function_call']['arguments'])['python_code'])
        code_list.append(code)
        flag = False
    except Exception as e :
        buffer = io.StringIO()
        traceback.print_exc(file=buffer)
        traceback_output = buffer.getvalue()
        error = '\n'.join(traceback_output.split('\n')[3:])
        error_list.append(error)
        print(error)
        buffer.close()
    finally:
        limit +=1