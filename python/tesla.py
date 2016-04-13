#/usr/bin/env python
import time
import datetime
import serial
import traceback
import requests
import smtplib
import json
import os
import sys
from multiprocessing import Process, Manager

import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

parkedDistInches = 45

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
        print 'please configure config.json'
        quit()

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
        print 'successfully sent the mail zz'
    except Exception, e:
        print "failed to send mail"
        print e

def calcKWHr(sumI, startChargeTime):
    dt = (datetime.datetime.now() - startChargeTime).total_seconds()/(60.0*60.0)
    kwHr = 0
    if len(sumI) > 0:
        kwHr = (sum(sumI)/float(len(sumI))) * .240 * dt

    return kwHr

def logTotalKwHr(kwHr):
    with open("log.csv", "a") as myfile:
        myfile.write(str(datetime.datetime.now()) + ', ' + str(kwHr))

def processCurrent(ser, sharedDict, configuration):
    count = 0
    update = 10
    prevI = 0
    startChargeTime = datetime.datetime.now()
    endChargeTime = datetime.datetime.now()
    fmt = "%Y-%m-%d %H:%M:%S %Z%z"

    sumI = []

    while True:
        try:
            count += 1
            line = ser.readline() #read ardiono about once every two seconds
            I  = float(line.split(' ')[1].strip())  #get the current reading
            sharedDict['I'] = I
            #currents bellow 1 amp are not accurate
            if I > 1:
                newupdate = 2 * 60 /2  #update google sheet once every two minutes
                if newupdate != update:
                    count = 0
                update = newupdate
            else:   #update google sheet once every hour
                update = 60 * 60 /2

                if(len(sumI) > 1):  #must be end of charge, send summary information
                    totalKwHr = calcKWHr(sumI, startChargeTime)
                    print 'total charge was ' + str(totalKwHr)
                    r = requests.get('http://docs.google.com/forms/d/'+configuration['googleFormTotalKW']+'/formResponse?ifq&entry.1201832211='+str(totalKwHr)+'&submit=Submit')
                    logTotalKwHr(totalKwHr)
                    
                sumI = []
                startChargeTime = datetime.datetime.now()

                

            #detect that car is plugged in and assume parked
            if I > 1:
                sharedDict['wasParked'] = True
                sharedDict['isParked'] = True

            if I > 3:
                sumI.append(I)
                endChargeTime = datetime.datetime.now()

            if count % update == 0 or abs(I - prevI) > .5: #update google sheet every time there is a change in curren tby more than .5 amp
                count = 0
                kwHr = calcKWHr(sumI, startChargeTime)
                print 'update spreadsheet ' + str(I) + ' - ' + str(kwHr)
                newUpdate = 'http://docs.google.com/forms/d/'+configuration['googleFormRealTimeKW']+'/formResponse?ifq&entry.2094522101='+str(I)+'&entry.33110511='+str(kwHr)+'&submit=Submit'
                print newUpdate
                r = requests.get(newUpdate)

            prevI = I
        except Exception, e:
            traceback.print_exc()

def processProximity(ser, sharedDict, configuration):
    keepLooping = True
    parkCount = 0

    if 'wasParked' not in sharedDict:
        print 'wasParked not is shared Dict'
        sharedDict['wasParked'] = False
    if 'isParked' not in sharedDict:
        print 'isParked not is shared Dict'
        sharedDict['isParked'] = False

    while keepLooping:
        try:
            line = ser.readline() #read ardiono
            prox = parkedDistInches + 100
            try:
                proxStr = line.split(' ')[1].replace('in,', '').strip()
                prox = int(proxStr)
            except Exception, e:
                pass

            sharedDict['prox'] = prox
            sharedDict['parkCount'] = parkCount

            if prox < parkedDistInches:


                if parkCount > 120:
                    sharedDict['isParked'] = True

                    if(sharedDict['isParked'] and not sharedDict['wasParked']):
                        print 'need to send a reminder'
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

                                               
        except Exception, e:
            keepLooping = False
            print e

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
        except Exception, e:
            print e
            
        print msg
        time.sleep(5)

def main():
    if len(sys.argv) > 1:
        print "cmd arg to set directory to: " + sys.argv[1]
        os.chdir(sys.argv[1])

    print 'cwd is: ' + os.getcwd()
        
    #make sure we have the correct device

    keepTrying = True
    countCurrent = 0
    countCurrentFail = 0;

    manager = Manager()
    sharedDictionay = manager.dict()

    configuration = readconfig()

    while keepTrying:
        serial0 = serial.Serial('/dev/ttyACM0') #connection to arduino1
        serial1 = serial.Serial('/dev/ttyACM1') #connection to arduino2
        
        try:
            line = ser.readline() #read ardiono about once every two seconds
            I  = float(line.split(' ')[1].strip())  #get the current reading
            countCurrent += 1
        except Exception, e:
            countCurrentFail +=1

        if countCurrent > countCurrentFail + 5: #5 good readings
            keepTrying = False
            p1 = Process(target=processCurrent, args=(serial0,sharedDictionay,configuration,))
            p2 = Process(target=processProximity, args=(serial1,sharedDictionay,configuration,))
            p1.start()
            p2.start()
            processOutput(sharedDictionay)
        elif countCurrentFail > countCurrent +5:  #5 bad readings, do a swap
            keepTrying = False
            p1 = Process(target=processCurrent, args=(serial1,sharedDictionay,configuration,))
            p2 = Process(target=processProximity, args=(serial0,sharedDictionay,configuration,))
            p1.start()
            p2.start()
            processOutput(sharedDictionay)

        print ' . ' + str(countCurrent) + '-' + str(countCurrentFail)
        


if __name__ == "__main__":
    main()
