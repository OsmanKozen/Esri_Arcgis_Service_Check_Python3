# Demonstrates how to check a folder for stopped services and print them.
# The messages could alternatively be written to an e-mail or log file.
# This script could be scheduled to run at a regular interval.
# encoding=utf8
# For Http calls
import http.client, urllib.request, urllib.parse, urllib.error, json

# For system tools
import sys, datetime

# For reading passwords without echoing
import getpass

from django.shortcuts import render
from django.template.loader import render_to_string
import numpy as np
import pandas as pd
import cx_Oracle, pymssql
import os
os.environ["NLS_LANG"] = "American_America.UTF8"

# Defines the entry point into the script
def main(argv=None):

    conRepoZeka = cx_Oracle.connect('User/pass@TNS', encoding="UTF-8",nencoding="UTF-8")
    curRepoZeka = conRepoZeka.cursor()

    arcgis_drop_sql = "Truncate table ARCGIS_SERVICE_CHECK"
    curRepoZeka.execute(arcgis_drop_sql)
    conRepoZeka.commit()

    # Print some info
    print()
    print("This tool is a sample script that detects stopped services in a folder.")
    print()  
    
    # Ask for admin/publisher user name and password
    #username = input("Enter user name: ")
    #password = getpass.getpass("Enter password: ")

    folderNames = ['Service1', 'Service2', 'Service3', 'Service4', 'Service5', 'Service6', 'Service7']
    serverNames = ['10.10.10.10', '10.10.10.11']

    for folderName in folderNames:

        for serverName in serverNames:

            username, password, serverName, serverPort, folder = 'user', 'pass', serverName, '6080', folderName
            
            if serverName == "10.10.10.10":
                CLUSTER_NO = "1"
            else:
                CLUSTER_NO = "2"

            # Ask for server name
            #serverName = input("Enter server name: ")
            #serverPort = 6080

            #folder = input("Enter the folder name or ROOT for the root location: ")

            # Create a list to hold stopped services
            stoppedList = []
            startedList = []
            
            # Get a token
            token = getToken(username, password, serverName, serverPort)
            if token == "":
                print("Could not generate a token with the username and password provided.")
                return
            
            # Construct URL to read folder
            if str.upper(folder) == "ROOT":
                folder = ""
            else:
                folder += "/"
                    
            folderURL = "/arcgis/admin/services/" + folder
            
            # This request only needs the token and the response formatting parameter 
            params = urllib.parse.urlencode({'token': token, 'f': 'json'})
            
            headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
            
            # Connect to URL and post parameters    
            httpConn = http.client.HTTPConnection(serverName, serverPort)
            httpConn.request("POST", folderURL, params, headers)
            
            # Read response
            response = httpConn.getresponse()
            if (response.status != 200):
                httpConn.close()
                print("Could not read folder information.")
                return
            else:
                data = response.read()
                
                # Check that data returned is not an error object
                if not assertJsonSuccess(data):          
                    print("Error when reading folder information. " + str(data))
                else:
                    print("Processed folder information successfully. Now processing services...")

                # Deserialize response into Python object
                dataObj = json.loads(data.decode('utf-8'))
                httpConn.close()

                # Loop through each service in the folder and stop or start it    
                for item in dataObj['services']:

                    fullSvcName = item['serviceName'] + "." + item['type']
            
                    # Construct URL to stop or start service, then make the request                
                    statusURL = "/arcgis/admin/services/" + folder + fullSvcName + "/status"

                    httpConn.request("POST", statusURL, params, headers)
                    
                    # Read status response
                    statusResponse = httpConn.getresponse()
                    if (statusResponse.status != 200):
                        httpConn.close()
                        print("Error while checking status for " + fullSvcName)
                        return
                    else:
                        statusData = statusResponse.read()
                                    
                        # Check that data returned is not an error object
                        if not assertJsonSuccess(statusData):
                            print("Error returned when retrieving status information for " + fullSvcName + ".")
                            print(str(statusData))

                        else:
                            # Add the stopped service and the current time to a list
                            statusDataObj = json.loads(statusData.decode('utf-8'))
                            if statusDataObj['realTimeState'] == "STOPPED":
                                stoppedList.append([fullSvcName,str(datetime.datetime.now())])
                            else:
                                startedList.append([fullSvcName,str(datetime.datetime.now())])

                                        
                    httpConn.close()           

            # Check number of stopped services found
            if len(stoppedList) == 0:
                # Started services, insert to DB
                print("No stopped services detected in folder " + folder.rstrip("/"))
            else:
                # Write out all the stopped services found
                # This could alternatively be written to an e-mail or a log file

                # Stopped services, insert to DB
                MAP_LAYER_STATUS = 0

                for item in stoppedList:
                    MAP_LAYER_NAME = item[0].rstrip(".MapServer")
                    APP_SERVICE_NAME = folder.rstrip("/")
                    CLUSTER = serverName

                    arcgis_insert = """INSERT INTO ARCGIS_SERVICE_CHECK VALUES ('{0}', '{1}', '{2}', '{3}', '{4}')""".format(CLUSTER, APP_SERVICE_NAME, MAP_LAYER_NAME, MAP_LAYER_STATUS, CLUSTER_NO)
                    curRepoZeka.execute(arcgis_insert)
                    conRepoZeka.commit()            
                    print("Service " + item[0] + " was detected to be stopped at " + item[1])

            # Check number of started services found
            if len(startedList) == 0:
                # Started services, insert to DB
                    
                for item in startedList:
                    print("No started services detected in folder " + folder.rstrip("/"))
            else:
                # Write out all the stopped services found
                # This could alternatively be written to an e-mail or a log file

                # Started services, insert to DB
                MAP_LAYER_STATUS = 1  

                for item in startedList:
                    MAP_LAYER_NAME = item[0].rstrip(".MapServer")
                    APP_SERVICE_NAME = folder.rstrip("/")
                    CLUSTER = serverName

                    arcgis_insert = """INSERT INTO ARCGIS_SERVICE_CHECK VALUES ('{0}', '{1}', '{2}', '{3}', '{4}')""".format(CLUSTER, APP_SERVICE_NAME, MAP_LAYER_NAME, MAP_LAYER_STATUS, CLUSTER_NO)
                    curRepoZeka.execute(arcgis_insert)
                    conRepoZeka.commit()
                    print("Service " + item[0] + " was detected to be started at " + item[1])

    curRepoZeka.close()

    return


# FUNCTIONS

# A function to generate a token given username, password and the adminURL.
def getToken(username, password, serverName, serverPort):
    # Token URL is typically http://server[:port]/arcgis/admin/generateToken
    tokenURL = "/arcgis/admin/generateToken"
    
    params = urllib.parse.urlencode({'username': username, 'password': password, 'client': 'requestip', 'f': 'json'})
    
    headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
    
    # Connect to URL and post parameters
    httpConn = http.client.HTTPConnection(serverName, serverPort)
    httpConn.request("POST", tokenURL, params, headers)
    
    # Read response
    response = httpConn.getresponse()
    if (response.status != 200):
        httpConn.close()
        print("Error while fetching tokens from admin URL. Please check the URL and try again.")
        return
    else:
        data = response.read()
        httpConn.close()
        
        # Check that data returned is not an error object
        if not assertJsonSuccess(data):            
            return
        
        # Extract the token from it
        token = json.loads(data.decode('utf-8'))        
        return token['token']            
        

# A function that checks that the input JSON object 
#  is not an error object.
def assertJsonSuccess(data):
    obj = json.loads(data.decode('utf-8'))
    if 'status' in obj and obj['status'] == "error":
        print("Error: JSON object returns an error. " + str(obj))
        return False
    else:
        return True
    
        
# Script start
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
