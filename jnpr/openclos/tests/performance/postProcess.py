'''
Created on Jan 8, 2015

@author: ubuntu
'''
putCablingPlan = []
putDeviceConfiguration = []
getDevices = []
getIpFabric = [] 

def main():
    outFile = open("out.csv","w") # open file for appending
    
    with open ("locust.csv", "r") as locust:
        for line in locust:
            if 'cabling-plan' in line:
                putCablingPlan.append(line)
            elif 'device-configuration' in line:
                putDeviceConfiguration.append(line)
            elif 'devices' in line:
                getDevices.append(line)
            elif 'GET' in line and 'ip-fabrics/' in line and 'devices' not in line:
                getIpFabric.append(line)
            elif 'None' in line and 'Total' in line:
                lastLine = line
            else:
                outFile.write(line)
    outFile.write(aggregate(putCablingPlan))
    outFile.write(aggregate(putDeviceConfiguration))
    outFile.write(aggregate(getDevices))
    outFile.write(aggregate(getIpFabric))
    outFile.write('\n')
    outFile.write(lastLine)
    outFile.close()
    
    
def aggregate(requests):
    #"Method","Name","# requests","# failures","Median response time","Average response time","Min response time","Max response time","Average Content Size","Requests/s"
    #"PUT","/openclos/ip-fabrics/000a63e2-2f3c-4c62-a09c-989902c35022/cabling-plan",4,0,520,563,503,687,0,0.03
    
    noOfRequest = 0
    failure = 0
    median = 0
    average = 0
    mins = []
    maxs = []
    contentSize = 0
    reqPerSec = 0.0
    params = []
    
    for request in requests:
        params = request.split(',')
        noOfRequest += int(params[2])
        failure += int(params[3])
        median += int(params[4])
        average += int(params[5])
        mins.append(int(params[6]))
        maxs.append(int(params[7]))
        contentSize += int(params[8])
        reqPerSec += float(params[9])
        
    rowCount = len(requests)
    nameSplit = params[1].split('/')
    nameSplit[3] = '<fabric id>'
    if len(nameSplit) == 4:
        nameSplit[3] += '"'
    out = [params[0], '/'.join(nameSplit), str(noOfRequest), str(failure), str(int(median/rowCount)), str(int(average/rowCount)), 
           str(min(mins)), str(max(maxs)), str(int(contentSize)), str(round(reqPerSec/rowCount, 2))+'\n']
    return ','.join(out)
    
if __name__ == '__main__':
    main()
    
