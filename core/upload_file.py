import pandas as pd
import json
from core.login import run_until_complete
from main import DataManager
import io


def parse_json_users(uploaded_file):
    json_data = json.load(uploaded_file)
    user_dicts = []
    for _, user in json_data.items():
        user_dict = {
                "id" : user.get('id'),
                "username": user.get('username'),
                "groups": user.get("groups")
                }
        user_dicts.append(user_dict)

    for user in user_dicts: 
        #There are users with null values for username and groups. 1496462258
        if user['groups'] is not None:
            run_until_complete(DataManager.add_user(user))


def parse_xls_users(uploaded_file):
    contents = uploaded_file.getvalue()
    with pd.ExcelFile(contents) as file:
        xls = pd.read_excel(file)
    xls['User ID'] = xls['User ID'].map(lambda x: int(x) if str(x).isdigit() else None)
    
    user_dicts = []
    for index, row in xls.iterrows():
        user_dict = {
                "id": row['User ID'],
                "username": row['Username']
                }
        user_dicts.append(user_dict)

  #  for user in user_dicts:
  #      run_until_complete(DataManager.add_user(user))



