import re
import pymongo
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pyquery import PyQuery

MONGO_URL = 'localhost'
MONGO_DB = 'taobao'
MONGO_TABLE = 'products'

#我们通过PyMongo库里的MongoClient，参数MONGO_URL是mongobd的地址，默认端口
client = pymongo.MongoClient(MONGO_URL)
#创建数据库名称
db = client[MONGO_DB]

browser = webdriver.Chrome()        #首先构造Webdriver对象，使用的浏览器是Chrome
#等待加载时间，使用WebDriver（）对象，可以指定等待条件，同时指定一个最长等待时间，这里设置的是10s。
#如果在这个时间内匹配了等待时间，也就是说页面元素成功加载出来了，即立即返回相应结果并继续向下执行，否则到了最大等待时间还没有加载出来时，就直接抛出超时异常
wait = WebDriverWait(browser, 10)
browser.maximize_window()           #将浏览器最大化

#定义search方法
def search():
    #异常处理，超过加载时间，重新调用search方法
    try:
        browser.get('https://www.taobao.com/')      #首先访问了搜索商品的链接
        #等待页面加载完成，首先获取页码输入框，赋值为input
        input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#q")))
        #获取“搜索”按钮，赋值为submit
        submit = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#J_TSearchForm > div.search-button > button")))
        input.send_keys('美食')                     #调用send_keys()方法将美食填充到输入框中
        submit.click()                              #点击“搜索”按钮
        #等待最下方页面数量加载完成
        total = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#mainsrp-pager > div > div > div > div.total')))
        get_products()                              #调用页面解析方法
        return total.text                           #返回该产品页码总数
    except TimeoutException:
        return search()

#定义next_page方法，翻页操作
def next_page(page_number):
    #异常处理，超时加载则重新翻页
    try:
        #等待“到第几页”的框加载完成
        input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#mainsrp-pager > div > div > div > div.form > input")))
        #等待“到第几页”的右边“确定”按钮加载完成
        submit = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#mainsrp-pager > div > div > div > div.form > span.btn.J_Submit")))
        input.clear()                       #首先清除输入框，调用clear（）方法
        input.send_keys(page_number)        #调用send_keys()方法将页码填充到输入框中
        submit.click()                      #然后点击“确定”按钮即可
        #这里将高亮的页码节点对应的CSS选择器和当前要跳转的页码通过参数传递给这个等待条件，这样它就会检测当前高亮的页码节点是不是我们传过来的页码数
        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, '#mainsrp-pager > div > div > div > ul > li.item.active > span'), str(page_number)))
        #调用当前页数的宝贝解析方法
        get_products()
    except TimeoutException:
        next_page(page_number)

#解析商品列表，这里直接获取源代码，利用pyquery进行解析
def get_products():
    #等待商品列表加载完成
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#mainsrp-itemlist .items .item')))
    html = browser.page_source                                          #调用page_source属性获取页码的源代码
    doc = PyQuery(html)                                                 #构造PyQuery解析对象
    items = doc('#mainsrp-itemlist .items .item').items()               #提取商品列表，会匹配整个页面的每个商品
    #for循环将每个结果分别进行解析，每次循环把它赋值给item变量，每个item变量都是一个PyQuery对象，然后调用它的find（）方法，传入CSS选择器，就可以获取单个商品的特定内容
    for item in items:
        #所有提取结果赋值为一个字典product
        product = {
            'image': item.find('.pic .img').attr('src'),                #图片
            'price': item.find('.price').text().replace('\n', ''),      #价格
            'deal': item.find('.deal-cnt').text()[:-3],                 #付款人数、取开始到倒数第三个
            'title': item.find('.title').text().replace('\n', ''),      #商品名称
            'shop': item.find('.shop').text(),                          #店铺名称
            'location': item.find('.location').text()                   #店铺地址
        }
        print(product)                  #打印商品详细信息
        save_to_mongo(product)          #调用sava_to_mongo方法，存储到MongoDB数据库中

#定义save_to_mongo方法，存储数据到MongoDB数据库中
def save_to_mongo(result):
    try:
        #直接调用insert()方法将数据插入到MongoDB，此处的result变量就是在get_products()方法里传来的product，包含单个商品的信息
        if db[MONGO_TABLE].insert(result):
            print("存储到MongDB成功", result)
    except Exception:
        print("存储到MongoDB失败", result)

def main():
    total = search()                                            #页数（共100页），当时该商品是100页
    total = int(re.compile('(\d+)').search(total).group(1))     #正则取出100数字
    for i in range(2, total + 1):       #next_page()方法需要接收参数page_number，page_number代表页码，这里实现页码遍历即可
        next_page(i)
    browser.close()                     #爬完数据，关闭浏览器

if __name__ == '__main__':              #模块是被直接运行的，则代码块被运行
    main()                              #调用main()方法
