#/usr/bin/env python
import time
import datetime
import serial
import traceback
import requests
import smtplib
import json
import thread
import os
import sys
from multiprocessing import Process, Manager

count = 0
update = 10
prevI = 0;
parkedDistInches = 45;
fmt = "%Y-%m-%d %H:%M:%S %Z%z"
startChargeTime = datetime.datetime.now()

#form1 = '1_v-XDRNcJMoK46hGEg2ZAEZ_7BJm6Vbx6vY7L2UlkZZ' #total
#form2 = '1e8dcuI-Z1jk8mapxdnSsRfkMdEI3KonJBKlyqNCYfZZ' #realTime


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

def send_email(user, pwd, recipient, subject, body):
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

def calcKWHr(sumI):
        dt = (datetime.datetime.now() - startChargeTime).total_seconds()/(60.0*60.0)
        kwHr = 0
        if len(sumI) > 0:
            kwHr = (sum(sumI)/float(len(sumI))) * .240 * dt

        return kwHr

def processCurrent(ser, sharedDict, configuration):
    global count
    global update
    global prevI
    startChargeTime = datetime.datetime.now()
    endChargeTIme = datetime.datetime.now()
    lastNagTime = datetime.datetime.min
    firstNag = datetime.timedelta(hours = 24)
    secondNag = datetime.timedelta(hours =72)

    sumI = []

    while True:
        try:
            count += 1
            line = ser.readline() #read ardiono about once every two seconds
            I  = float(line.split(' ')[1].strip())  #get the current reading
            #currents bellow 1 amp are not accurate
            if I > 1:
                newupdate = 2 * 60 /2  #update google sheet once every two minutes
                if newupdate != update:
                    count = 0
                update = newupdate
            else:   #update google sheet once every hour
                update = 60 * 60 /2

                if(len(sumI) > 1):  #must be end of charge, send summary information
                    totalKwHr = calcKWHr(sumI)
                    print 'total charge was ' + str(totalKwHr)
                    r = requests.get('http://docs.google.com/forms/d/'+configuration['googleFormTotalKW']+'/formResponse?ifq&entry.1201832211='+str(totalKwHr)+'&submit=Submit')
                sumI = []
                startChargeTime = datetime.datetime.now()

            #detect that car is plugged in and assume parked
            if I > 1:
                sharedDict['wasParked'] = True
                sharedDict['isParked'] = True

            if I > 3:
                sumI.append(I)
                endChargeTIme = datetime.datetime.now()
                lastNagTime = datetime.datetime.now()
            elif datetime.datetime.now() - endChargeTIme > firstNag and datetime.datetime.now() - lastNagTime > secondNag:
                lastNagTime = datetime.datetime.now()
                print 'send reminder'
                server = smtplib.SMTP('smtp.gmail.com:587')
                server.starttls()
                server.login(configuration['emailFromAddr'],configuration['emailFromPassword'])
                FROM = 'Tessa'
                TO = ['Da'] # must be a list
                SUBJECT = ""
                TEXT = 'last chrg: ' + endChargeTIme.strftime(fmt)
                # Prepare actual message

                message = """From: %s To: %s
    Subject: Time to Charge!%s

    %s
                """ % (FROM, ", ".join(TO), SUBJECT, TEXT)

                print message

                server.sendmail(configuration['emailFromAddr'], configuration['emailToAddr'], message)#'From: Tessa last chrg: ' + endChargeTIme.strftime(fmt))
                server.quit()
            print str(count) + '-' + str(update) + ' '  + str(I)
            if count % update == 0 or abs(I - prevI) > .5: #update google sheet every time there is a change in curren tby more than .5 amp
                count = 0

                kwHr = calcKWHr(sumI)
                print 'update spreadsheet ' + str(I) + ' - ' + str(kwHr)
                r = requests.get('http://docs.google.com/forms/d/'+configuration['googleFormRealTimeKW']+'/formResponse?ifq&entry.2094522101='+str(I)+'&entry.33110511='+str(kwHr)+'&submit=Submit')
                #print r.text
            prevI = I
        except Exception, e:
            traceback.print_exc()

def sendTxt(fromEmail, password, toEmail):
    try:
        print fromEmail + '   ' +password
        server = smtplib.SMTP('smtp.gmail.com:587')
        server.ehlo()
        server.starttls()
        server.login(fromEmail,password)
        
        FROM = 'Tessa'
        TO = ['Da'] # must be a list
        SUBJECT = ""
        TEXT = 'time to charge' #'last chrg: ' + endChargeTIme.strftime(fmt)
        # Prepare actual message

        message = """From: %s To: %s
    Subject: Time to Charge!%s

    %s
        """ % (FROM, ", ".join(TO), SUBJECT, TEXT)

        print message

        server.sendmail(fromEmail, toEmail, message)#'From: Tessa last chrg: ' + endChargeTIme.strftime(fmt))
        server.quit()
    except Exception, e:
        print 'EXCEPTION IN SENDTXT'
        print e

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

            print 'proximity inches is ' + str(prox) + ' count is ' + str(parkCount)

            if prox < parkedDistInches:


                if parkCount > 10:
                    sharedDict['isParked'] = True

                    if(sharedDict['isParked'] and not sharedDict['wasParked']):
                        print 'need to send a reminder'
                        #sendTxt(configuration['emailFromAddr'], configuration['emailFromPassword'], configuration['emailToAddr'])
                        send_email(configuration['emailFromAddr'], configuration['emailFromPassword'], configuration['emailToAddr'], 'Remember to charge', 'Tessa may not be plugged in!'):

                    sharedDict['wasParked'] = True

                parkCount += 1
                if parkCount > 300:
                    parkCount = 300

                print 'parking ' + str(parkCount)
            else:
                parkCount -= 1
                if parkCount < 0:
                    parkCount = 0
                    sharedDict['wasParked'] = False
                    sharedDict['isParked'] = False

                                               
        except Exception, e:
            keepLooping = False
            print e


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
            p1.join()
            p2.join()
        elif countCurrentFail > countCurrent +5:  #5 bad readings, do a swap
            keepTrying = False
            p1 = Process(target=processCurrent, args=(serial1,sharedDictionay,configuration,))
            p2 = Process(target=processProximity, args=(serial0,sharedDictionay,configuration,))
            p1.start()
            p2.start()
            p1.join()
            p2.join()

        print ' . ' + str(countCurrent) + '-' + str(countCurrentFail)
        


if __name__ == "__main__":
    main()
