import json
import urllib.request,urllib.parse
import ssl
from xml.etree import ElementTree
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from numpy.random import seed
from numpy.random import randint
import asdf
seed(2)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HOST = "192.168.1.254"
USER = "apiadmin"
PWRD = "@Clockwis3"

VRTRS = []
ZONES = []

class XmlDictConfig(dict):
    '''
    Example usage:

    >>> tree = ElementTree.parse('your_file.xml')
    >>> root = tree.getroot()
    >>> xmldict = XmlDictConfig(root)

    Or, if you want to use an XML string:

    >>> root = ElementTree.XML(xml_string)
    >>> xmldict = XmlDictConfig(root)

    And then use xmldict for what it is... a dict.
    '''
    def __init__(self, parent_element):
        if parent_element.items():
            self.update(dict(parent_element.items()))
        for element in parent_element:
            if element:
                # treat like dict - we assume that if the first two tags
                # in a series are different, then they are all different.
                if len(element) == 1 or element[0].tag != element[1].tag:
                    aDict = XmlDictConfig(element)
                # treat like list - we assume that if the first two tags
                # in a series are the same, then the rest are the same.
                else:
                    # here, we put the list in dictionary; the key is the
                    # tag name the list elements all share in common, and
                    # the value is the list itself
                    aDict = {element[0].tag: XmlListConfig(element)}
                # if the tag has attributes, add those to the dict
                if element.items():
                    aDict.update(dict(element.items()))
                self.update({element.tag: aDict})
            # this assumes that if you've got an attribute in a tag,
            # you won't be having any text. This may or may not be a
            # good idea -- time will tell. It works for the way we are
            # currently doing XML configuration files...
            elif element.items():
                self.update({element.tag: dict(element.items())})
            # finally, if there are no child tags and no attributes, extract
            # the text
            else:
                self.update({element.tag: element.text})
class api:
    '''
    Structure that contains API connection information and API Key
    '''
    def __init__(self,hostname,user,pwrd):
        self.hostname = hostname
        self.user = user
        self.pwrd = pwrd
    key = ''

def getXMLInterfaceComments(interface,api):
    url = 'https://{}/api/?'.format(api.hostname)
    cmd = 'get'
    xpath = "/config/devices/entry[@name='localhost.localdomain']/network/interface/ethernet/entry[@name='{}']".format(interface)
    param = {'type':'config','action':cmd,'xpath':xpath,'key':api.key}
    try:
        response = requests.get(url,params=param, verify=False)
        if response.status_code==200:
            root = ElementTree.fromstring(response.text)
            mydict = {}
            xmldict = XmlDictConfig(root)
            if ("comment" in str(xmldict['result']['entry'])):
                mydict[str(xmldict['result']['entry']['name'])] = xmldict['result']['entry']['comment']
                return(mydict)
            else:
                mydict[str(xmldict['result']['entry']['name'])] = ""
                return(mydict)
    except requests.HTTPError as e:
        print(e.errno)

def genINT():
    return randint(1,9999,1)

def getKey(api):
    '''
    Given an instantiated API class with hostname, username, and password
    return valid API key for API calls
    :param api:
    :return:
    '''
    url = "https://{0}/api/?type=keygen&user={1}&password={2}".format(api.hostname,api.user,api.pwrd)
    request = urllib.request.urlopen(url,context=ctx)
    if (request.getcode() == 200):
        response = str(request.read())
        return (str(response).split('<key>')[1].split('</key>')[0])

def createTunnel(next,api):
    tunnel_name = "tunnel.{}".format(next)
    mydata = { "entry": [
                {
                    '@name': tunnel_name,
                    'comment':'AUTO-GENERATED'
                }
            ]
        }

    headers ={"X-PAN-KEY" : api.key}
    url = 'https://{}/restapi/v9.1/Network/TunnelInterfaces'.format(api.hostname)
    params = {"name":"tunnel.{}".format(next)}
    try:
        response = requests.post(url,params=params,json=mydata,headers=headers,verify=False)
        if (response.status_code == 200):
            return tunnel_name
        else:
            return response
    except requests.HTTPError as e:
        print(e)

def getNextTunnel(api):
    '''
    Automatically chooses tunnel interface if not specified (pending upcoming UI considerations)
    There will be a button to specify tunnel number or one will be autogenerated
    :param api:
    :return:
    '''
    req = urllib.request.Request('https://{}/restapi/v9.1/Network/TunnelInterfaces'.format(api.hostname))
    req.add_header('X-PAN-KEY',api.key)
    req.add_header('Content-Type','application/json')
    resp = urllib.request.urlopen(req,context=ctx)
    if resp.getcode()==200:
        d = json.loads(resp.read())
        index = int(d['result']['@count'])-1
        nextTunnel = (int(d['result']['entry'][index]['@name'].split('tunnel.')[1]) + 1)
        if nextTunnel < 10000:
            return nextTunnel
        else:
            tunID = []
            print("Max tunnel subinterface value in use- generating random tunnel interface")
            for item in d['result']['entry']:
                tunID.append(item['@name'])
            ID = int(genINT())
            i=1
            while ID in tunID:
                i+=1
                seed(i)
                ID = int(genINT())
            print("selected "+str(ID))
            return int(ID)

def getVRTRMembers(vRTR,api):
    headers = {"X-PAN-KEY": api.key}
    url = 'https://{}/restapi/v9.1/Network/VirtualRouters'.format(api.hostname)
    params = {"name": "{}".format(vRTR)}
    try:
        response = requests.get(url, params=params, headers=headers, verify=False)
        return json.loads(response.text)['result']['entry'][0]['interface']['member']
    except requests.HTTPError as e:
        print(e)

def getZoneMembers(zone,api):
    headers = {"X-PAN-KEY": api.key}
    url = 'https://{}/restapi/v9.1/Network/Zones'.format(api.hostname)
    params = {"name": "{}".format(zone),"@location":"vsys","@vsys":"vsys1"}
    try:
        response = requests.get(url, params=params, headers=headers, verify=False)
        return json.loads(response.text)['result']['entry'][0]['network']['layer3']['member']
    except requests.HTTPError as e:
        print(e)


def assoc_vRTR(vRTR,tunnel,api):
    members = getVRTRMembers(vRTR,api)
    members.append(tunnel)

    mydata = {"entry": [
        {
            '@name': vRTR,
            'interface': {
                'member' : members
            }
        }
    ]
    }
    headers ={"X-PAN-KEY" : api.key}
    url = 'https://{}/restapi/v9.1/Network/VirtualRouters'.format(api.hostname)
    params = {"name":"{}".format(vRTR)}
    try:
        response = requests.put(url, json=mydata, params=params, headers=headers, verify=False)
        if response.status_code == 200:
            print("Tunnel '{0}' successfully associated to Virtual Route '{1}'.".format(tunnel,vRTR))
        else:
            print("HTTP "+response.status_code)
            print(response.reason)
    except requests.HTTPError as e:
        print(e)

def assoc_Zone(zone,tunnel,api):
    members = getZoneMembers(zone,api)
    members.append(tunnel)
    mydata = {"entry": [
        {
            '@name': zone,
            'network': {
                'layer3': {
                        'member' : members
                    }
                }
            }
      ]
    }
    headers ={"X-PAN-KEY" : api.key}
    url = 'https://{}/restapi/v9.1/Network/Zones'.format(api.hostname)
    params = {"name": "{}".format(zone),"@location":"vsys","@vsys":"vsys1"}
    try:
        response = requests.put(url, json=mydata, params=params, headers=headers, verify=False)
        if response.status_code==200:
            print("Tunnel '{0}' successfully associated to Zone '{1}'.".format(tunnel,zone))
        else:
            print("HTTP " + response.status_code)
            print(response.reason)
    except requests.HTTPError as e:
        print(e)

def init_vRTR(api):
    url = "https://{}/restapi/v9.1/Network/VirtualRouters".format(api.hostname)
    headers = {"X-PAN-KEY": api.key}
    response = requests.get(url,headers=headers,verify=False)
    mydict = json.loads(response.text)

    for item in mydict['result']['entry']:
        VRTRS.append(item['@name'])
    print("vRTRs initialized")

def init_zones(api):
    url = "https://{}/restapi/v9.1/Network/Zones".format(api.hostname)
    headers = {"X-PAN-KEY": api.key}
    params = {"@location":"vsys","@vsys":"vsys1"}

    try:
        response = requests.get(url,headers=headers,params=params,verify=False)
    except requests.HTTPError as e:
        print(e)

    mydict = json.loads(response.text)

    for item in mydict['result']['entry']:
        ZONES.append(item['@name'])

    print("Zones initialized")

def getInterfaces(api):
    url="https://192.168.1.254/restapi/v9.1/Network/EthernetInterfaces"
    headers = {"X-PAN-KEY": api.key}

    response = requests.get(url,headers=headers,verify=False)
    entries = json.loads(response.text)
    interfaces = []
    for i in range(0,int(entries['result']['@total-count'])):
        interfaces.append(entries['result']['entry'][i])

    return interfaces


x = api(HOST,USER,PWRD)
x.key = (getKey(x))
#init_vRTR(x)
#init_zones(x)

#newTun = createTunnel(getNextTunnel(x),x)
#assoc_vRTR('default',newTun,x)
#assoc_Zone('WAN',newTun,x)

#for i in range(1,8):
#    print(getXMLInterfaceComments('ethernet1/{}'.format(str(i)),x))
for item in getInterfaces(x):
    print(item)
