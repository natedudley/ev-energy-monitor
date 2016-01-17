#/usr/bin/env python
import time
import datetime
import serial
import traceback
import requests
import smtplib

ser = serial.Serial('/dev/ttyACM0') #connection to arduino

count = 0
update = 10
prevI = 0;
fmt = "%Y-%m-%d %H:%M:%S %Z%z"

srcEmailAddr = 'joesmith@gmail.com'
srcEmailPwd = 'supersecretpassword'
dstEmailAddr = '4252060411@txt.att.net'
form1 = '1_v-XDRNcJMoK46hGEg2ZAEZ_7BJm6Vbx6vY7L2UlkZZ'
form2 = '1e8dcuI-Z1jk8mapxdnSsRfkMdEI3KonJBKlyqNCYfZZ'


startChargeTime = datetime.datetime.now()
endChargeTIme = datetime.datetime.now()
lastNagTime = datetime.datetime.min
firstNag = datetime.timedelta(hours = 24)
secondNag = datetime.timedelta(hours =72)

sumI = []

def calcKWHr():
    dt = (datetime.datetime.now() - startChargeTime).total_seconds()/(60.0*60.0)
    kwHr = 0
    if len(sumI) > 0:
        kwHr = (sum(sumI)/float(len(sumI))) * .240 * dt

    return kwHr

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
                totalKwHr = calcKWHr()
                print 'total charge was ' + str(totalKwHr)
                r = requests.get('http://docs.google.com/forms/d/'+form1+'/formResponse?ifq&entry.1201832211='+str(totalKwHr)+'&submit=Submit')
            sumI = []
            startChargeTime = datetime.datetime.now()
            
        if I > 3:
            sumI.append(I)
            endChargeTIme = datetime.datetime.now()
            lastNagTime = datetime.datetime.now()
        elif datetime.datetime.now() - endChargeTIme > firstNag and datetime.datetime.now() - lastNagTime > secondNag:
            lastNagTime = datetime.datetime.now()
            print 'send reminder'
            server = smtplib.SMTP('smtp.gmail.com:587')
            server.starttls()
            server.login(srcEmailAddr,srcEmailPwd)
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

            server.sendmail(srcEmailAddr, dstEmailAddr, message)#'From: Tessa last chrg: ' + endChargeTIme.strftime(fmt))
            server.quit()
        print str(count) + '-' + str(update) + ' '  + str(I)
        if count % update == 0 or abs(I - prevI) > .5: #update google sheet every time there is a change in curren tby more than .5 amp
            count = 0
            
            kwHr = calcKWHr()
            print 'update spreadsheet ' + str(I) + ' - ' + str(kwHr)
            r = requests.get('http://docs.google.com/forms/d/'+form2+'/formResponse?ifq&entry.2094522101='+str(I)+'&entry.33110511='+str(kwHr)+'&submit=Submit')
            #print r.text
        prevI = I
    except Exception, e:
        traceback.print_exc()
