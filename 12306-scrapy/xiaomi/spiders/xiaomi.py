from scrapy.spiders import Spider, Request #CrawlSpider与Rule配合使用可以起到历遍全站的作用、Request干啥的我就不解释了
from scrapy import FormRequest #Scrapy中用作登录使用的一个包
from ..stations import stations
import time
import json
import re
import urllib.parse
import random
import configparser


class MyConfigParser(configparser.ConfigParser):
    def __init__(self, defaults=None):
        configparser.ConfigParser.__init__(self, defaults=defaults)

    def optionxform(self, optionstr):
        return optionstr


class XiaomiSpider(Spider):
    name = 'xiaomi'
    allowed_domains = ['12306.cn']
    header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 '
                            '(KHTML, like Gecko) Chrome/65.0.3325.146 Safari/537.36'}  # 设置浏览器用户代理
    train = None
    key_check_isChange = None
    repeattoken = None
    cookiejar = 1

    usr = None
    pwd = None
    usr_name = None
    usr_IDcard = None
    usr_phnum = None
    seat_type = None
    seat_type_code = None
    usr_type = None
    usr_type_code = None

    from_station = None
    from_station_code = None
    to_station = None
    to_station_code = None

    lastest = None
    earliest = None
    date = None

    passengerTicketStr = None
    oldPassengerStr = None
    cp = None

    def start_requests(self):
        self.cp = MyConfigParser()
        self.cp.read("conf/conf.ini")

        self.usr = self.cp['user_info']['user']
        self.pwd = self.cp['user_info']['pwd']
        self.usr_name = self.cp['user_info']['usrname']
        self.usr_IDcard = self.cp['user_info']['usrIDcard']
        self.usr_phnum = self.cp['user_info']['usrphnum']

        self.seat_type = self.cp['user_info']['seat_type']
        self.usr_type = self.cp['user_info']['usr_type']
        self.usr_type_code = self.cp['user_type_code'][self.usr_type]

        self.from_station = self.cp['station_info']['from_station']
        self.from_station_code = stations.get(self.from_station)
        self.to_station = self.cp['station_info']['to_station']
        self.to_station_code = stations.get(self.to_station)

        self.earliest = self.cp['station_info']['earliest']
        self.lastest = self.cp['station_info']['lastest']
        self.date = self.cp['station_info']['date']

        print('start_requests')
        yield Request("http://www.12306.cn/mormhweb/", meta={'cookiejar': self.cookiejar}, headers=self.header)

    def parse(self, response):
        """
            获取验证码
        """
        code_url = r'https://kyfw.12306.cn/passport/captcha/captcha-image?' \
                   r'login_site=E&module=login&rand=sjrand&{}'.format(random.random())
        print('获取验证码图片：'+code_url)
        return Request(code_url, meta={'cookiejar': self.cookiejar},
                       callback=self.code_submit)

    def code_submit(self, response):
        print('验证码获取ing')
        with open('conf/code.png', 'wb') as fn:
            fn.write(response.body)
        print('验证码获取成功')
        vcode_position = ['43,47', '43,47', '114,35', '186,37', '255,39', '40,111', '111,107', '177,112', '252,113']
        position = input("请输入验证码位置:").split(',')
        data_vcode_position = []
        for point in position:
            data_vcode_position.append(vcode_position[int(point)])
        code = ','.join(data_vcode_position)
        formdata = {
            'answer': code,
            'login_site': 'E',
            'rand': 'sjrand'
        }
        url = 'https://kyfw.12306.cn/passport/captcha/captcha-check'
        print('验证码 START')
        return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar}, callback=self.login)

    def login(self, response):
        data = re.findall(r'(\w*[0-9]+)\w*', response.body.decode())
        if data[0] == '4':
            print('验证码 SUCCESS')
            return self.login_module()
        else:
            print('验证码 FAILED，重新填写验证')
            return self.parse(response)

    def login_module(self):
        url = 'https://kyfw.12306.cn/passport/web/login'
        formdata = {
            'username': self.usr,
            'password': self.pwd,
            'appid': 'otn'
        }
        print('用户名密码登录 START')
        return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar},
                           callback=self.after_login)

    def after_login(self, response):
        data = re.findall(r'(\w*[0-9]+)\w*', response.body.decode())
        if data[0] == '0':
            print('登录 SUCCESS')
            formdata = {
                'appid': 'otn',
            }
            url = 'https://kyfw.12306.cn/passport/web/auth/uamtk'
            print('uamtk START')
            return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar}, callback=self.umatk)
        else:
            print('登录 FAILED，请检查用户名及密码')

    def umatk(self, response):
        jdata = json.loads(response.body.decode())
        if jdata['result_code'] == 0:
            print('umatk SUCCESS')
            formdata = {
                'tk': jdata['newapptk']
            }
            url = 'https://kyfw.12306.cn/otn/uamauthclient'
            print('uamtkclient START')
            return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar}, callback=self.umatkauthclient)
        else:
            print('umatk FAILED,请重试')

    def umatkauthclient(self, response):
        jdata = json.loads(response.body.decode())
        if jdata['result_code'] == 0:
            print('umatkauthclient SUCCESS')
            return self.query_module()
        else:
            print('umatkauthclient FAILED')

    def query_module(self):
        url = ('https://kyfw.12306.cn/otn/leftTicket/queryO?'
               'leftTicketDTO.train_date={}&'
               'leftTicketDTO.from_station={}&'
               'leftTicketDTO.to_station={}&'
               'purpose_codes={}').format(self.date, self.from_station_code, self.to_station_code, self.usr_type)
        print('查询班次 START')
        return Request(url, meta={'cookiejar': self.cookiejar},
                       callback=self.get_train_data, dont_filter=True)

    def get_train_data(self, response):
        # print('get_train_data:', json.loads(response.body.decode()))
        jdata = json.loads(response.body.decode())
        if jdata['status'] is True:
            print('查询班次 SUCCESS')
            data = jdata['data']['result']
            for train_data in data:
                train = train_data.split('|')
                if self.lastest >= train[8] >= self.earliest and train_strategy(self, train):
                    print('有票')
                    self.train = train
                    formdata = {
                        '_json_att': ''
                    }
                    url = 'https://kyfw.12306.cn/otn/login/checkUser'
                    print('checkUser 开始')
                    return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar},
                                       callback=self.order_submit)
            print('无票，重新请求')
        else:
            print('查询班次 FAILED, RETRY')
        time.sleep(1)
        return self.query_module()

    def order_submit(self, response):
        print('order_submit:', json.loads(response.body.decode()))
        jdata = json.loads(response.body.decode())
        if jdata['status'] is True:
            print('checkUser SUCCESS')
            secret_str = urllib.parse.unquote(self.train[0])
            formdata = {
                'secretStr': secret_str,
                'train_date': self.date,
                'back_train_date': time.strftime("%Y-%m-%d"),
                'tour_flag': 'dc',
                'purpose_codes': self.usr_type,
                'query_from_station_name': self.from_station,
                'query_to_station_name': self.to_station,
                'undefined': ''
            }
            url = 'https://kyfw.12306.cn/otn/leftTicket/submitOrderRequest'
            print('提交订单 START')
            return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar},
                               callback=self.initc)
            # if result['status'] == True:
            #     print('提交订单请求成功')
            #     return True
            # else:
            #     print('提交订单请求失败,稍后将进行重试...如果多次失败,请检查是否有未支付订单...')
            #     time.sleep(5)
            #     submit_Order_Request(request, secret_str)
            # return Request(lnk, meta={'cookiejar': self.cookiejar}, callback=self.cart_process_1)
        else:
            print('checkUser FAILED')

    def initc(self, response):
        print('initc:', json.loads(response.body.decode()))
        jdata = json.loads(response.body.decode())
        if jdata['status'] is True:
            print('submitOrderRequest SUCCESS')
            formdata = {
                '_json_att': '',
            }
            url = 'https://kyfw.12306.cn/otn/confirmPassenger/initDc'
            print('initDc START')
            return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar}, headers=self.header,
                               callback=self.paDTOs)
        else:
            print('submitOrderRequest FAILED')

    def paDTOs(self, response):
        self.repeattoken = response.xpath('/html/head/script[1]').extract()[0].split(';')[1].split('\'')[1]
        b1 = re.search(r'key_check_isChange.+', response.body.decode()).group().split(',')[0]
        key_check_ischange = re.sub(r'(key_check_isChange)|(\')|(:)', '', b1)
        self.key_check_isChange = key_check_ischange
        formdata = {
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': self.repeattoken
        }
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/getPassengerDTOs'
        print('getPassengerDTOs START')
        return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar}, headers=self.header,
                           callback=self.check_order)

    def check_order(self, response):
        print('check_order:', json.loads(response.body.decode()))
        jdata = json.loads(response.body.decode())
        if jdata['status'] is True:
            print('check_order SUCCESS')
            formdata = {
                'cancel_flag': '2',
                'bed_level_order_num': '000000000000000000000000000000',
                'passengerTicketStr': self.passengerTicketStr, #'1,0,1,李锐,1,371203199611193514,17805427953,N',
                'oldPassengerStr': self.oldPassengerStr, #'李锐,1,371203199611193514,1_',
                'tour_flag': 'dc',
                'randCode': '',
                'whatsSelect': '1',
                '_json_att': '',
                'REPEAT_SUBMIT_TOKEN': self.repeattoken
            }
            url = 'https://kyfw.12306.cn/otn/confirmPassenger/checkOrderInfo'
            print('checkOrderInfo START')
            return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar},
                               callback=self.getQueueCount)
        else:
            print('check_order FAILED')

    def getQueueCount(self, response):
        print('getQueueCount:', json.loads(response.body.decode()))
        jdata = json.loads(response.body.decode())
        if jdata['status'] is True:
            print('getQueueCount SUCCESS')
            formdata = {
                'train_date': formate_date(self.date),
                'train_no': self.train[2],
                'stationTrainCode': self.train[3],
                'seatType': self.seat_type,
                'fromStationTelecode': self.train[6],
                'toStationTelecode': self.train[7],
                'leftTicket': self.train[12],
                'purpose_codes': '00',
                'train_location': self.train[15],
                '_json_att': '',
                'REPEAT_SUBMIT_TOKEN': self.repeattoken
            }
            url = 'https://kyfw.12306.cn/otn/confirmPassenger/getQueueCount'
            print('getQueueCount START')
            return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar},
                               callback=self.final)
        else:
            print('getQueueCount FAILED')

    def final(self, response):
        print('check_order:', json.loads(response.body.decode()))
        jdata = json.loads(response.body.decode())
        if jdata['status'] is True:
            print('final SUCCESS')
            formdata = {
                'passengerTicketStr': self.passengerTicketStr,
                'oldPassengerStr': self.oldPassengerStr,
                'randCode': '',
                'purpose_codes': '00',
                'key_check_isChange': self.key_check_isChange,
                'leftTicketStr': self.train[12],
                'train_location': self.train[15],
                'choose_seats': '',
                'seatDetailType': '000',
                'whatsSelect': '1',
                'roomType': '00',
                'dwAll': 'N',
                '_json_att': '',
                'REPEAT_SUBMIT_TOKEN': self.repeattoken
            }
            url = 'https://kyfw.12306.cn/otn/confirmPassenger/confirmSingleForQueue'
            print('confirmSingleForQueue START')
            # return FormRequest(url, formdata=formdata, meta={'cookiejar': self.cookiejar},
            #                    callback=self.ok)
        else:
            print('final FAILED')

    @staticmethod
    def ok(response):
        print('ALL FINISHED')
        pass


def train_strategy(self, train):
    """
    -8 动卧
    -8 硬座
    -9 硬卧
    -11 无座
    -14 软卧
    :return:
    """
    seat_type_list = []
    for seatItem in self.seat_type.split(','):
        seat_type_list.append(self.cp.get('seat_type_code', seatItem))
    if (self.cp['seat_type_code']['DW'] in seat_type_list) and train[-4] != ('无' or ''):
        self.seat_type_code = self.cp['seat_type_code']['DW']
    elif (self.cp['seat_type_code']['RW'] in seat_type_list) and train[-14] != ('无' or ''):
        self.seat_type_code = self.cp['seat_type_code']['RW']
    elif (self.cp['seat_type_code']['YW'] in seat_type_list) and train[-9] != ('无' or ''):
        self.seat_type_code = self.cp['seat_type_code']['YW']
    elif (self.cp['seat_type_code']['YZ'] in seat_type_list) and train[-8] != ('无' or ''):
        self.seat_type_code = self.cp['seat_type_code']['YZ']
    else:
        return False
    self.passengerTicketStr = self.cp.get('passenger_info', 'passengerTicketStr').\
        format(self.seat_type_code, self.usr_type_code, self.usr_name, self.usr_IDcard, self.usr_phnum)
    self.oldPassengerStr = self.cp.get('passenger_info', 'oldPassengerStr').\
        format(self.usr_name, self.usr_IDcard, self.usr_type+'_')
    return True


def formate_date(traindate):
    """
        将传递的字符串转化为时间
        :param : 时间： 2017-12-29
        :return: Fri Dec 29 2017 00:00:00 GMT+0800 (中国标准时间)
    """
    ts = time.mktime(time.strptime(traindate, "%Y-%m-%d"))
    s = time.ctime(ts)
    t1 = s[0:11] + s[20:] + " 00:00:00 GMT+0800 (中国标准时间)"
    return t1
