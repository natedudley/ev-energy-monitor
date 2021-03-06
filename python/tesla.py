#/usr/bin/env python
import time
import datetime; from dateutil.relativedelta import *
import serial
import requests
import smtplib
import json
import os
import sys
from multiprocessing import Process, Manager
from google.cloud import firestore

import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

datastore_client = None

parkedDistInches = 45

#application depends on json file to configure gmail sender and google drive location for posting data
def readconfig():
    try:
        f = open('config.json', 'r')
        j = json.load(f)
        return j
    except IOError:
        configuration = {'emailFromAddr':'joesmith@gmail.com',
             'emailFromPassword':'supersecretpassword',
             'emailToAddr': '4252060411@txt.att.net',
             'googleFormTotalKW': 'asdfasdfasdfasdf',
             'googleFormRealTimeKW': 'asdfasdfasdfasdf'}
        json.dump(configuration, open("config.json",'w'), sort_keys=True, indent=4,)
        print('please configure config.json')
        quit()

#sends reminder email via gmail
def sendEmail(user, pwd, recipient, subject, body):
    gmail_user = user
    gmail_pwd = pwd
    FROM = user
    TO = recipient if type(recipient) is list else [recipient]
    SUBJECT = subject
    TEXT = body

    # Prepare actual message
    message = """\From: %s\nTo: %s\nSubject: %s\n\n%s
    """ % (FROM, ", ".join(TO), SUBJECT, TEXT)
    try:
        # SMTP_SSL Example
        server_ssl = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server_ssl.ehlo() # optional, called by login()
        server_ssl.login(gmail_user, gmail_pwd)
        # ssl server doesn't support or need tls, so don't call server_ssl.starttls()
        server_ssl.sendmail(FROM, TO, message)
        #server_ssl.quit()
        server_ssl.close()
        print ('successfully sent the mail zz')
    except Exception as e:
        print ("failed to send mail")
        print (e)

#uses the sample readings and total charge time to calculate KwHr
def calcKWHr(sumI, startChargeTime):
    dt = (datetime.datetime.now() - startChargeTime).total_seconds()/(60.0*60.0)
    kwHr = 0
    if len(sumI) > 0:
        kwHr = (sum(sumI)/float(len(sumI))) * .240 * dt

    return kwHr

#file logger as backup incase internet is down
def logTotalKwHr(kwHr):
    try:
        doc = datastore_client.collection('totalCharge').document('allTimeSum')
        storedTotal = doc.get().to_dict()['kwHr']
        doc.set({'kwHr': (storedTotal + kwHr)})
    except Exception as e:
        print ("failed firestore allTimeSum")
        print (e)
        
    try:
        byMonthdoc = datastore_client.collection('byMonth').document('records')
        byMonthDict = byMonthdoc.get().to_dict()
        orderbyMonthDoc = datastore_client.collection('byMonth').document('keyOrder')
        keyOrderbyMonth = orderbyMonthDoc.get().to_dict()['list']
        dateStr = datetime.datetime.now().strftime("%b%-y")
        
        if not dateStr in byMonthDict:
            byMonthDict[dateStr] = 0
            keyOrderbyMonth.append(dateStr)
            orderbyMonthDoc.set({'list': keyOrderbyMonth})
            
        byMonthDict[dateStr] += kwHr
        byMonthdoc.set(byMonthDict)    
        
        
    except Exception as e:
        print ("failed firestore month sum")
        print (e)
    
    
    try:
        key = datastore_client.collection('totalCharge').document()
        key.set({
            'timeStamp': datetime.datetime.utcnow(),
            'I': 0,
            'kwHr': kwHr
        })
    except Exception as e:
        print ("failed firestore totalCharge")
        print (e)
        
    with open("log.csv", "a") as myfile:
        myfile.write(str(datetime.datetime.now()) + ', ' + str(kwHr) + '\n')

#run as a thread to read the current sensing arduino via serial port
def processCurrent(ser, sharedDict, configuration):
    startChargeTime = datetime.datetime.now()
    endChargeTime = datetime.datetime.now()
    fmt = "%Y-%m-%d %H:%M:%S %Z%z"
    
    updateActiveCharge = {
        'freq' : relativedelta(hours=2),
        'lastUpdateTime' : (datetime.datetime.now() - relativedelta(hours=2)),
        'prevI': 0
    }
    
    sumI = []

    while True:
        try:
            line = ser.readline().decode("utf-8") #read ardiono about once every two seconds
            I  = float(line.split(' ')[1].strip())  #get the current reading
            sharedDict['I'] = I
            sharedDict['timeToNextLog'] = ((updateActiveCharge['lastUpdateTime']+updateActiveCharge['freq']) - datetime.datetime.now())

            if I < 3:
                if len(sumI) > 1:  #must be end of charge, send summary information
                    totalKwHr = calcKWHr(sumI, startChargeTime)
                    print ('total charge was ' + str(totalKwHr))
                    r = requests.get('http://docs.google.com/forms/d/'+configuration['googleFormTotalKW']+'/formResponse?ifq&entry.1201832211='+str(totalKwHr)+'&submit=Submit')
                    logTotalKwHr(totalKwHr)
                    
                sumI = []
                startChargeTime = datetime.datetime.now()
            else:
                #detect that car is plugged in and assume parked
                sharedDict['wasParked'] = True
                sharedDict['isParked'] = True
                sumI.append(I)
                endChargeTime = datetime.datetime.now()

            if abs(I - updateActiveCharge['prevI']) > 2:
                updateActiveCharge['freq'] = relativedelta(seconds=10)
                
            if datetime.datetime.now() - updateActiveCharge['freq'] > updateActiveCharge['lastUpdateTime']:
                updateActiveCharge['lastUpdateTime'] = datetime.datetime.now()
                if I > 5:
                    updateActiveCharge['freq'] = relativedelta(minutes=5)
                else:
                    updateActiveCharge['freq'] = relativedelta(hours=3)
                    
                updateActiveCharge['prevI'] = I
                
                
                kwHr = calcKWHr(sumI, startChargeTime)
                print ('update charge status ' + str(I) + ' - ' + str(kwHr))
                
                try:
                    key = datastore_client.collection('activeCharge').document()
                    key.set({
                        'timeStamp': datetime.datetime.utcnow(),
                        'I': I,
                        'kwHr': kwHr
                    })
                    key = datastore_client.collection('activeCharge').document('now')
                    key.set({
                        'timeStamp': datetime.datetime.utcnow(),
                        'I': I,
                        'kwHr': kwHr
                    })
                except Exception as e:
                    print ("failed firestore activeCharge")
                    print (e)
                
                try:
                    activeCharge_ref = datastore_client.collection('activeCharge')
                    now = datetime.datetime.now() - relativedelta(days=+14)
                    docs = activeCharge_ref.where('timeStamp', '<', now).order_by('timeStamp',
                                                                 direction=firestore.Query.ASCENDING).limit(10).stream()
                    for doc in docs:
                        datastore_client.collection('activeCharge').document(doc.id).delete()
                    
                except Exception as e:
                    print ("failed firestore delete activeCharge")
                    print (e)
                
        except Exception as e:
            print(e)

#run as a thread to read the proximity sensing arduino via serial port
def processProximity(ser, sharedDict, configuration):
    keepLooping = True
    parkCount = 0

    if 'wasParked' not in sharedDict:
        print ('wasParked not in shared Dict')
        sharedDict['wasParked'] = True
    if 'isParked' not in sharedDict:
        print ('isParked not in shared Dict')
        sharedDict['isParked'] = False

    while keepLooping:
        try:
            line = ser.readline().decode("utf-8") #read ardiono
            prox = parkedDistInches + 100
            try:
                proxStr = line.split(' ')[1].replace('in,', '').strip()
                prox = int(proxStr)
            except Exception as e:
                pass

            sharedDict['prox'] = prox
            sharedDict['parkCount'] = parkCount

            if prox < parkedDistInches:


                if parkCount > 120:
                    sharedDict['isParked'] = True

                    if(sharedDict['isParked'] and not sharedDict['wasParked']):
                        print ('need to send a reminder')
                        sendEmail(configuration['emailFromAddr'], configuration['emailFromPassword'], configuration['emailToAddr'], 'Remember to charge', 'Tessa may not be plugged in!')

                    sharedDict['wasParked'] = True

                parkCount += 1
                if parkCount > 300:
                    parkCount = 300
            else:
                parkCount -= 1
                if parkCount < 0:
                    parkCount = 0
                    sharedDict['wasParked'] = False
                    sharedDict['isParked'] = False

                                               
        except Exception as e:
            keepLooping = False
            print (e)

#console print out of status
def processOutput(sharedDict):
    while True:
        msg = ''
        try:
            if 'prox' in sharedDict:
                msg = msg + str(sharedDict['prox']) + '\" '
            if 'parkCount' in sharedDict:
                msg = msg + 'parkCnt ' + str(sharedDict['parkCount']) + ' '
            if 'I' in sharedDict:
                msg = msg + 'I ' + str(sharedDict['I'] )+ ' '
            if 'inetStatus' in sharedDict:
                msg = msg + 'inet' + str(sharedDict['inetStatus']) + ' '
            if 'wasParked' in sharedDict:
                msg = msg + 'wasParked: ' + str(sharedDict['wasParked']) + ' '
            if 'isParked' in sharedDict:
                msg = msg + 'isParked: ' + str(sharedDict['isParked']) + ' '
            if 'timeToNextLog' in sharedDict:
                msg = msg + 'timeToNextLog: ' + str(sharedDict['timeToNextLog'].total_seconds()) + ' '

        except Exception as e:
            print (e)
            
        print (msg)
        time.sleep(5)

#test if internet is working
#todo if internet is down, true to bring it back up
def testInternet(sharedDict, url='http://www.google.com/', timeout=5):
    while True:
        try:
            _ = requests.get(url, timeout=timeout)
            sharedDict['inetStatus'] = 'up'
        except requests.ConnectionError:
            print("No internet connection available.")
            sharedDict['inetStatus'] = 'down'
        time.sleep(600)

#kick off the threads
def startThreading(sharedDictionary, iSerial, proxSerial):
    configuration = readconfig()
    pCurrent = Process(target=processCurrent, args=(iSerial,sharedDictionary,configuration,))
    pProx = Process(target=processProximity, args=(proxSerial,sharedDictionary,configuration,))
    pInet = Process(target=testInternet, args=(sharedDictionary,))
    pCurrent.start()
    pProx.start()
    pInet.start()

    #don't do the last one as a thread to keep the python app up
    processOutput(sharedDictionary)


def main():
    if len(sys.argv) > 1:
        print ("cmd arg to set directory to: " + sys.argv[1])
        os.chdir(sys.argv[1])

    print ('cwd is: ' + os.getcwd())
    
    
    try:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "keys/rainorshine98040-firestore_user.json"
        global datastore_client
        datastore_client = firestore.Client()
    except Exception as e:
        print ("to connect to google firestore")
        print (e)
        time.sleep(15)
        
    #make sure we have the correct device

    keepTrying = True
    countCurrent = 0
    countCurrentFail = 0;

    manager = Manager()
    sharedDictionary = manager.dict()

    while keepTrying:
        serial0 = serial.Serial('/dev/ttyACM0') #connection to arduino1
        serial1 = serial.Serial('/dev/ttyACM1') #connection to arduino2
        
        line = serial1.readline().decode("utf-8") #read ardiono about once every two seconds
        print('startup: ' + line)
            
        try:
            
            I  = float(line.split(' ')[1].strip())  #get the current reading
            countCurrent += 1
            
        except Exception as e:
            countCurrentFail +=1

        if countCurrent > countCurrentFail + 5: #5 good readings
            keepTrying = False
            startThreading(sharedDictionary, serial1, serial0)
        elif countCurrentFail > countCurrent +5:  #5 bad readings, do a swap
            keepTrying = False
            startThreading(sharedDictionary, serial0, serial1)

        print (' . ' + str(countCurrent) + '-' + str(countCurrentFail))

if __name__ == "__main__":
    main()
