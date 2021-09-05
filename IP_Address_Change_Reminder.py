import smtplib
import json
import requests
from bs4 import BeautifulSoup
import time
import datetime
import logging
import logging.config
from email.mime.text import MIMEText
from email.header import Header
import re

CONFPATH = 'conf.json'
logging.config.fileConfig('log.conf')
logger = logging.getLogger('root')

def ReadConfig(configPath, rwopt):
    config = ''
    try:
        with open(configPath, rwopt, encoding='utf-8') as jsonFile:
            config = json.load(jsonFile)
        jsonFile.close()
    except Exception as e:
        logger.fatal("Loading configure file failed: " + configPath)
        exit(0)
    logger.info("Loading configure file successful: " + configPath)
    return config

def GetPublicIpAddress():
    requestIpUrl="http://ip.42.pl/raw"
    try:
        reponse = requests.get(requestIpUrl)   
        responseIpAddress = reponse.text
    except Exception as e:
        logger.warning("GetPublicIpAddress() Failed to obtain public network address, retrying...")
        return 'Failed'
    logger.info("GetPublicIpAddress() Successfully obtained public network address: " + responseIpAddress)
    return responseIpAddress

def GetPublicIpAddressCN():
    requestIpUrl="http://www.ip111.cn/"
    try:
        reponse = requests.get(requestIpUrl)
        reponse.encoding='utf-8'
        reponseHTML=reponse.text
        soup = BeautifulSoup(reponseHTML,'html.parser')
        soup1 = soup.find_all('div', class_='card-body')[0].find_all('p')[0].string
        result = re.findall(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b", soup1)
        if result:
            logger.info("GetPublicIpAddressCN() Successfully obtained public network address: " + result[0])
            return result[0]
        else:
            logger.warning("GetPublicIpAddressCN() Failed to obtain public network address, retrying...")       
            return 'Failed'
    except Exception as e:
        logger.warning("GetPublicIpAddressCN() Failed to obtain public network address, retrying...")
        return 'Failed'

def SendWechat(config,messageTitle,messageStr):
    if(config['remindServerChan']['enable'] == "true"):
        logger.info("Config['remindServerChan']['enable'] value is : true ,should send Wechat message")
        sckey = config['remindServerChan']['sckey']
        logger.debug("Your ServerChan Token: " + sckey)
        reqStr = "https://sc.ftqq.com/" + sckey + ".send"
        try:
            reponse = requests.get(reqStr,params={'text': messageTitle, 'desp': messageStr})
            logger.debug("HTTP GET Reponse :" + reponse.text.encode('utf-8').decode('unicode_escape'))
        except Exception as e:
            logger.error("Failed to send WechatMessage")

def SendWechatPushBear(config,messageTitle,messageStr):
    if(config['remindPushBear']['enable'] == "true"):
        logger.info("Config['remindPushBear']['enable'] value is : true ,should send WechatPushBear message")
        SendKey = config['remindPushBear']['SendKey']
        logger.debug("Your PushBearn Token: " + SendKey)
        reqStr = "https://pushbear.ftqq.com/sub"
        try:
            reponse = requests.get(reqStr,params={'sendkey': SendKey, 'text': messageTitle, 'desp': messageStr}) 
            logger.debug("HTTP GET Reponse :" + reponse.text.encode('utf-8').decode('unicode_escape'))
        except Exception as e:
            logger.error("Failed to send remindPushBearMessage")


def SendMessage(config,messageStr):
    if(config['remindMail']['enable'] == "true"):
        logger.info("Config['remindMail']['enable'] value is : true ,should send message")
        smtp_host = config['remindMail']['smtp_host']
        smtp_user = config['remindMail']['smtp_user']
        smtp_pass = config['remindMail']['smtp_pass']
        sender = config['remindMail']['sender']
        receivers = config['remindMail']['receivers']
        subject = 'IP address has been updated'
        message = MIMEText(messageStr, 'plain', 'utf-8')
        message['From'] = Header("Alert", 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')
        try:
            smtpObj = smtplib.SMTP()
            smtpObj.connect(smtp_host, 25)
            smtpObj.login(smtp_user,smtp_pass)
            smtpObj.sendmail(sender, receivers, message.as_string())
            logger.info("Mail sent successfully")
        except smtplib.SMTPException:
            logger.error("Failed to send mail")

def SendWeCom(config,content):
    if(config['remindWeCom']['enable'] == "true"):
        logger.info("Config['remindWeCom']['enable'] value is : true ,should send message")
        try:
            reponse = requests.get('https://qyapi.weixin.qq.com/cgi-bin/gettoken',
                                   params={'corpid': config['remindWeCom']['corpid'], 'corpsecret': config['remindWeCom']['corpsecret']})
            access_token = reponse.json()['access_token']

            message_dic = {
                'touser': config['remindWeCom']['receivers_userid'],
                'toparty': '',
                'totag': '',
                'msgtype': 'text',
                'agentid': config['remindWeCom']['agentid'],
                'text': {
                    'content': content
                },
                'safe': 0,
                'enable_id_trans': 0,
                'enable_duplicate_check': 0,
                'duplicate_check_interval': 1800,
            }
            message_json = json.dumps(message_dic)

            reponse = requests.post('https://qyapi.weixin.qq.com/cgi-bin/message/send',
                                    params={'access_token': access_token},
                                    data=message_json)
            logger.info("WeComMsg sent successfully")
        except Exception as e:
            logger.error("Failed to send WeComMsg")

def UpdateRecord(config):
    conf_ip = config['public_ip']
    try:
        new_ip = GetPublicIpAddressCN()
        if(not conf_ip == new_ip and not new_ip == 'Failed'):
            logger.info("IP address has been updated")     
            config['public_ip'] = new_ip
            with open(CONFPATH, 'w+') as new_conf:
                json.dump(config, new_conf, indent=4)
            new_conf.close()
            logger.info("Update record successfully")
            return True
        else:
            return False
    except Exception as e:
        logger.error("Failed to Update record")
        return False

def main():
    while(True):
        CONFIG_FILE = ReadConfig(CONFPATH, 'r')     
        CYCLE_PERIOD = CONFIG_FILE['cycle_period']
        timeNow = datetime.datetime.now()
        timeNow.strftime("%Y/%m/%d %H:%M:%S")

        boolUpdated = UpdateRecord(CONFIG_FILE)
        if(boolUpdated):
            msgTitle = "公网IP地址变更提醒"
            msgText = "The public IP address of the node you are following has been updated. The new address is: " + CONFIG_FILE['public_ip']
            SendMessage(CONFIG_FILE, msgText)
            SendWechat(CONFIG_FILE, msgTitle, msgText)
            SendWechatPushBear(CONFIG_FILE, msgTitle, msgText)
            SendWeCom(CONFIG_FILE,msgText)
    
        timeNext = timeNow + datetime.timedelta(seconds = 60*CYCLE_PERIOD)
        logger.info("Next Check Time: " + str(timeNext))

        time.sleep(60*CYCLE_PERIOD)

if __name__ == '__main__':
    main()