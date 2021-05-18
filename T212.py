from datetime import datetime, timedelta,date
import csv,traceback, requests as r,sys, pandas as pd,time
sys.path.insert(0,'C:/Finance/projects/')
import env,googleapi as gapi
import selenium.webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
T212data = []
bf = pd.DataFrame()
baseRestUrl = "https://live.trading212.com/rest/history"
StartDate = datetime.strptime('2020-03-01T00:00:00','%Y-%m-%dT%H:%M:%S')
EndDate = datetime.strptime('2021-01-15T23:59:59','%Y-%m-%dT%H:%M:%S')
options = Options()
options.add_argument('user-data-dir=C:\\Users\\Administrator\\AppData\\Local\\Google\\Chrome\\User Data')
driver = selenium.webdriver.Chrome(executable_path= env.driver_path,  options  = options)
driver.get('https://live.trading212.com/')
def login():
    try:
        driver.find_element(By.XPATH, "/html/body/div[1]/section[2]/div/div/div/form/input[6]").click()
    except:
        pass
    WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH,"""//*[@id="layout"]""")))
    switch_mode('Invest')
    exportTransactions(StartDate,EndDate)
    switch_mode('ISA')
    exportTransactions(StartDate,EndDate)
    print("Writing transactions to Google Sheets...")
    env.rep_data_sh(bf,'18HjRhb8maIt0ypGxSAmjz592_1oQZqEN0f915RlGsjw','data',bf.shape[1])
    driver.quit()

def switch_mode(Type):
    """
    Switching the mode (Invest/ISA) then get cookies
    """
    button_id = "isaSwitchButton" if Type  != 'Invest' else "equitySwitchButton"
    driver.find_element(By.XPATH, """//*[@id="navigation"]/div[5]""").click()
    elem = WebDriverWait(driver, 10).until(expected_conditions.element_to_be_clickable((By.ID, button_id)))
    # If the button is active, you don't have to click on the button
    if "active" not in elem.get_attribute('class').split():
        elem.click()
        WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH,"""//*[@id="layout"]""")))
        print('Switching to {} account'.format(Type))
    else:
        driver.find_element_by_tag_name('body').send_keys(' ')
    cookies = driver.get_cookies()
    global cookies_dict
    cookies_dict = {}
    for cookie in cookies:
        cookies_dict[cookie['name']] = cookie['value']

def exportTransactions(StartDate, EndDate):
    delta = timedelta(hours = 6)
    while StartDate < EndDate:
        # if StartDate > datetime.strptime(datetime.strftime(StartDate,'%Y-%m-%d')+'T06:59:59','%Y-%m-%dT%H:%M:%S') and StartDate + timedelta(minutes = 359, seconds= 59) < datetime.strptime(datetime.strftime(StartDate,'%Y-%m-%d')+'T19:59:59','%Y-%m-%dT%H:%M:%S'):
        # print(StartDate, StartDate + timedelta(minutes = 359, seconds= 59))
        # fetchTransactions(StartDate+ timedelta(days=1), StartDate + delta)
        fetchTransactions(StartDate, StartDate + timedelta(minutes = 359, seconds= 59))
        time.sleep(0.5)
        # print("Fetching transactions between {} and {}".format(StartDate+ timedelta(days=1), StartDate + delta))
        StartDate += delta
    writeData()

def fetchTransactions(StartDate, EndDate):
    StartDateStr = StartDate.strftime('%Y-%m-%dT%H:%M:%S')+"%2B02:00"
    EndDateStr = EndDate.strftime('%Y-%m-%dT%H:%M:%S')+"%2B02:00"
    url = baseRestUrl + "/all?newerThan={}&olderThan={}".format(StartDateStr, EndDateStr) + '&frontend=WC4&filtered=false'
    resp = r.get(url, cookies=cookies_dict)
    transactions = resp.json()['data']
    print("{} to {} - {} transactions".format(StartDateStr, EndDateStr, len(transactions)))

    for transaction in transactions:
        try:
            processTransaction(transaction)
        except Exception as e:
            traceback.print_exc()
            print("Failed to process transaction")
            print(transaction)

def processTransaction(transaction):
    key = transaction["heading"]["key"]

    if key == "history.instrument":
        subKey = transaction["subHeading"]["key"]

        if subKey == "history.order.filled.buy":
            fetchTransactionDetails(transaction, "buy")
        elif subKey == "history.order.filled.sell":
            fetchTransactionDetails(transaction, "sell")
        elif subKey in ["history.order.buy", "history.order.sell"]:
            pass
        else:
            print("    Unknown transaction type {}. Skipping it".format(subKey))

def fetchTransactionDetails(transaction, orderType):
    url = baseRestUrl + transaction["detailsPath"]
    transaction = r.get(url, cookies=cookies_dict).json()
    prettyName = transaction["heading"]["context"]["prettyName"]
    symbol = transaction["heading"]["context"]["instrument"]
    instrumentCode = transaction["heading"]["context"]["instrumentCode"]
    tradeDate = findValue(transaction, "history.details.order.fill.date-executed.key")["date"]
    quantity = findValue(transaction, "history.details.order.fill.quantity.key")["quantity"]
    quantityPrecision = findValue(transaction, "history.details.order.fill.quantity.key")["quantityPrecision"]
    price = findValue(transaction, "history.details.order.fill.price.key")["amount"]
    currency = findValue(transaction, "history.details.order.fill.price.key")["currency"]
    fx = findValue(transaction, "history.details.order.exchange-rate.key")["quantity"]
    total = findValue(transaction, "history.details.order.total.key")["amount"]
    order_id = findValue(transaction, "history.details.order.fill.id.key")["id"]

    T212data.append({
            "Purchased Date": tradeDate[:10],
            "Order Type": orderType.capitalize(),
            "Symbol": symbol,
            "Comapany": prettyName,
            "Number of Shares":  quantity,#-quantity if orderType == 'sell' else quantity,
            "Purchased Price LC": price,# -price if orderType == 'sell' else price,
            "Purchased Price GBP": total/quantity, #-total/quantity if orderType == 'sell' else total/quantity,
            "FX":fx,#-fx if orderType == 'sell' else fx,
            "Currency": currency,
            "Purchased Time": tradeDate[11:16],
            "Total Purchase Price LC": price*quantity,#-price*quantity if orderType == 'sell' else price*quantity,
            "Total Purchase Price GBP": total, #-total if orderType == 'sell' else total,
            "NOSPrecision": quantityPrecision,
            "Order ID": order_id,
            "Fees": 0,
            'Stock Split Ratio':0
        })

    # sorted(T212data, key = lambda i: (i['Purchased Date'], i['Purchased Time']))
# Finds the value of a key in the transaction details API response

def findValue(transaction, key):
    for item in transaction["sections"]:
        if "description" in item and item["description"]["key"] == key:
            return item["value"]["context"]

        elif "rows" in item:
            for row in item["rows"]:
                if "description" in row and row["description"]["key"] == key:
                    return row["value"]["context"]
    raise Exception("Key: `{}` not found in transaction details".format(key))

def writeData():
    df = pd.DataFrame(T212data)
    dd = driver.execute_script("return dataLayer;")
    df['Account ID'] = dd[0]['accountId']
    df['Account Email'] = dd[0]['email']
    df['Account Trading Type'] = dd[0]['accountTradingType']
    sh = env.open_wb('18HjRhb8maIt0ypGxSAmjz592_1oQZqEN0f915RlGsjw').worksheet('manual data')
    df2 = pd.DataFrame(sh.get_all_values())
    df2.columns = df2.iloc[0] #make first row column anems
    df2 = df2[1:]
    df = pd.concat([df, df2], sort=False)
    global bf
    bf = df.append(bf)
    bf.drop_duplicates(inplace=True,  keep='first')
    bf.sort_values(['Purchased Date', 'Purchased Time'], ascending=True, inplace = True )

login()
