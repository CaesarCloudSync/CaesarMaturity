import os
import json
import base64
import hashlib
import asyncio 
import uvicorn
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Header,Request
from typing import Dict,List,Any,Union
from MaturitySQLDB.Maturitycrud import MaturityCRUD
from MaturitySQLDB.Maturityhash import MaturityHash
from fastapi.responses import StreamingResponse
from fastapi import WebSocket,WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from MaturityJWT.maturityjwt import MaturityJWT
from MaturitySQLDB.Maturity_create_tables import MaturityCreateTables
from SQLOps.sqlops import SQLOps

load_dotenv(".env")
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


maturitycrud = MaturityCRUD()

maturityjwt = MaturityJWT(maturitycrud)
Maturitycreatetables = MaturityCreateTables()
Maturitycreatetables.create(maturitycrud)
sqlops = SQLOps(maturitycrud,Maturitycreatetables)
JSONObject = Dict[Any, Any]
JSONArray = List[Any]
JSONStructure = Union[JSONArray, JSONObject]


@app.get('/')# GET # allow all origins all methods.
async def index():
    return "Hello World"
@app.post('/signupapi') # POST
async def signup(data: JSONStructure = None):
    try:
        signupdata = {}
        data = dict(data)
        hashed = hashlib.sha256(data["password"].encode('utf-8')).hexdigest()
        signupdata["email"] = data["email"]
        signupdata["password"] = hashed
        table = "users"
        condition = f"email = '{signupdata['email']}'"
        email_exists = maturitycrud.check_exists(("*"),"users",condition=condition)
        if email_exists:
            return {"message": "Email already exists"} # , 400
        elif not email_exists:

            res = maturitycrud.post_data(("email","password"),(signupdata["email"],signupdata["password"]),table=table)
            if res:
                access_token = maturityjwt.secure_encode({"email":signupdata["email"]})#create_access_token(identity=signupdata["email"])
                callback = {"status": "success","access_token":access_token}
            else:
                return {"error":"error when posting signup data."}
            return callback
    except Exception as ex:
        error_detected = {"error": "error occured","errortype":type(ex), "error": str(ex)}
        return error_detected
@app.post('/loginapi') # POST
async def login(login_details: JSONStructure = None): # ,authorization: str = Header(None)
    # Login API
    try:



        login_details = dict(login_details)
        #print(login_details)
        condition = f"email = '{login_details['email']}'"
        email_exists = maturitycrud.check_exists(("*"),"users",condition=condition)
        if email_exists:
            access_token = maturityjwt.provide_access_token(login_details,student=0)
            if access_token == "Wrong password":
                return {"message": "The username or password is incorrect."}
            else:
                return {"access_token": access_token}

        return {"message": "The username or password is incorrect."}
    except Exception as ex:
        return {"error": f"{type(ex)} {str(ex)}"}

@app.post('/storequestions') # POST # allow all origins all methods.
async def storequestion(data : JSONStructure = None, authorization: str = Header(None)):
    try:
        current_user = maturityjwt.secure_decode(authorization.replace("Bearer ",""))["email"]
        if current_user:
            data = dict(data)#request.get_json() # te
            maturityassessment,function,category,subcategory,questionrating,question,evidence,grade = sqlops.validate_store_request(data)
            email = current_user
            res = sqlops.store_question(email ,maturityassessment,function,category,grade ,subcategory,questionrating,question,evidence)
            if res:
                return {"message":"question was stored"}
            else:
                return {"error","questings already exist"}
            
            
    except Exception as ex:
        print(type(ex),ex)
        return {"error":f"{type(ex)},{ex}"}
@app.get('/getquestions') # POST # allow all origins all methods.
async def getquestions(request: Request,authorization: str = Header(None)):
    try:
        current_user = maturityjwt.secure_decode(authorization.replace("Bearer ",""))["email"]
        if current_user:
            #request.get_json() # tes,function,category,subcategory,questionrating = sqlops.validate_request(data)
            params = dict(request.query_params)
            has_access = sqlops.check_access(current_user,params["maturityassessment"])
            if has_access:

                res = maturitycrud.get_join_question_data(("maturityassessments.maturityassessment","functions.function","categorys.category","subcategorys.subcategory",
                                                     "questionratings.questionrating","questions.question","questions.evidenceforservice","maturityassessments.author_email",
                                                     "subcategorys.grade"),params)
                res_list = list({frozenset(item.items()) : item for item in res}.values())
                return {"maturityassessments":res_list}


            else:
                return {"error":"You are unauthorized to use this document."}  
    except Exception as ex:
        print(type(ex),ex)
        return {"error":f"{type(ex)},{ex}"}
@app.put('/updatequestion') # POST # allow all origins all methods.
async def updatequestion(data : JSONStructure = None,authorization: str = Header(None)):
    try:
        current_user = maturityjwt.secure_decode(authorization.replace("Bearer ",""))["email"]
        if current_user:
            #request.get_json() # tes,function,category,subcategory,questionrating = sqlops.validate_request(data)
            

            data = dict(data)
            has_access = sqlops.check_access(current_user,data["maturityassessment"])
            if has_access:
                #data_json = {"oldsubcategory":"PR.IR-2","subcategory":"GV.CV-1"}

                maturitycrud.update_maturityinfo(data)
                return {"message":"maturity data updated."}
            else:
                return {"error":"You are unauthorized to use this document."}  
    except Exception as ex:
        print(type(ex),ex)
        return {"error":f"{type(ex)},{ex}"}
@app.delete('/deletematurityinfo') # POST # allow all origins all methods.
async def deletematurityinfo(request : Request,authorization: str = Header(None)):
    try:
        current_user = maturityjwt.secure_decode(authorization.replace("Bearer ",""))["email"]
        if current_user:
            #request.get_json() # tes,function,category,subcategory,questionrating = sqlops.validate_request(data)
            
            params = dict(request.query_params)
            has_access = sqlops.check_access(current_user,params["maturityassessment"])
            if has_access:
                res = maturitycrud.delete_maturityinfo(params)

                return {"message":"maturity data deleted."}
            else:
                return {"error":"You are unauthorized to use this document."}  
    except Exception as ex:
        print(type(ex),ex)
        return {"error":f"{type(ex)},{ex}"}
@app.post('/grantaccess') # POST # allow all origins all methods.
async def grantaccess(data : JSONStructure = None, authorization: str = Header(None)):
    try:
        current_user = maturityjwt.secure_decode(authorization.replace("Bearer ",""))["email"]
        if current_user:
            data = dict(data)
            email = data["email"]
            maturityassessment = data["maturityassessment"]
            has_access = sqlops.check_access(current_user,maturityassessment)
            if has_access:
                email_exists = maturitycrud.check_exists(("*"),"users",f"email = '{email}'")
                if email_exists:
                    res = maturitycrud.post_data(("email","maturityassessment"),(email,maturityassessment),"maturityassessmentaccess")
                    if res:
                        return {"message":f"access has been granted to {email} for this maturity assesement."}
                    else:
                        return {"error":"error granting acccess."}
                else:
                    return {"message":"user doesn't exist."}
            else:
                return {"error":"You are unauthorized to grant access."}  

    except Exception as ex:
        print(type(ex),ex)
        return {"error":f"{type(ex)},{ex}"}
@app.delete('/removeaccess') # POST # allow all origins all methods.
async def removeaccess(request : Request, authorization: str = Header(None)):
    try:
        current_user = maturityjwt.secure_decode(authorization.replace("Bearer ",""))["email"]
        if current_user:
            params = dict(request.query_params)
            email = params["email"]
            maturityassessment = params["maturityassessment"]
            has_access = sqlops.check_access(current_user,maturityassessment)
            if has_access:
                res = maturitycrud.delete_data("maturityassessmentaccess",f"email = '{email}' AND maturityassessment = '{maturityassessment}'")
                if res:
                    return {"message":f"access has been remove from {email} for this maturity assesement."}
                else:
                    return {"error":"error granting acccess."}
            else:
                return {"error":"You are unauthorized to remove access."}  

    except Exception as ex:
        print(type(ex),ex)
        return {"error":f"{type(ex)},{ex}"}

async def main():
    config = uvicorn.Config("main:app", port=8080, log_level="info",reload=True) # ,host="0.0.0.0"
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    uvicorn.run("main:app",port=8080,log_level="info")
    #uvicorn.run()
    #asyncio.run(main())