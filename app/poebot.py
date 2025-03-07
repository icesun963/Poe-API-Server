from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from functools import wraps
from selenium.common.exceptions import WebDriverException, TimeoutException
import markdownify, time, secrets, string, os, glob
from config import config
import undetected_chromedriver as uc
from selenium.webdriver.common.proxy import Proxy, ProxyType

def handle_errors(func):
    @wraps(func)
    def wrapped_func(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except WebDriverException as e:
            print(f"An error occurred: {e}")
            self.kill_driver()
            time.sleep(3)
            self.start_driver()
    return wrapped_func

class PoeBot:
    def __init__(self):
        self.start_driver()
        
    def start_driver(self):
        isReady = False
        for i in range(30):
            try:
                self.start_driver_II()
                isReady=True
                break
            except Exception as e:
                print("error", e)
                self.kill_driver()
                time.sleep(3)
                print("retry...")
                
                pass
        if isReady==False:
            self.start_driver_II()

    def start_driver_II(self):
        if (config["cookie"] is None or config["bot"] is None):
            return
        
        PROXY = config.get("proxy","")
        options = webdriver.ChromeOptions()

        if PROXY!=None:
            options.add_argument('--proxy-server=' + PROXY)
            #options.add_argument("--ignore-certificate-errors")
            print("user proxy:" + '--proxy-server=' + PROXY)

        print("View:" + str(config.get("view","0")) + " " + str(config.get("view","0") !="1"))
        #options.add_argument("ignore-certificate-errors")
        
        self.driver = uc.Chrome(options=options, headless= config.get("view","0") !="1" )
        
        self.driver.get("https://poe.com/login?redirect_url=%2F")
        self.driver.add_cookie({"name": "p-b", "value": config['cookie']})
        self.driver.get(f"https://poe.com/{config['bot']}")
        
    
    @handle_errors
    def get_latest_message(self):
        bot_messages = self.driver.find_elements(By.XPATH, '//div[contains(@class, "Message_botMessageBubble__CPGMI")]')
        if bot_messages:
            latest_message = bot_messages[-1]
            if (latest_message.text == "..."):
                return None
            self.driver.execute_script('arguments[0].scrollIntoView();',latest_message)
            msg = markdownify.markdownify(latest_message.get_attribute("innerHTML"), heading_style="ATX")
            msg = msg.replace("\*", "*")
            return msg
        else:
            return None
    
    @handle_errors
    def abort_message(self):
        try:
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "ChatStopMessageButton_stopButton__LWNj6"))).click()
        except TimeoutException:
            return

    @handle_errors
    def send_message(self, message):
        if ("[TEXT]" in message):
            message = message.replace("[TEXT]", "")
            self.send_message_as_text(message)
        else:
            if (len(message) > config.get("send-as-text-limit", 200)):
                self.send_message_as_file(message)
            else:
                self.send_message_as_text(message)
        time.sleep(1)
        start_time = time.time()
        latest_message = ""
        latest_message_old = ""
        while True:
            bot_messages = self.driver.find_elements(By.XPATH, '//div[contains(@class, "Message_botMessageBubble__CPGMI")]')
            if bot_messages:
                latest_message_old = latest_message
                latest_message = bot_messages[-1].text
            if latest_message != "..." and latest_message_old!=latest_message:
                print("break:" + latest_message + " " +  latest_message_old)
                break
            if self.is_generating() == False and time.time() - start_time > 30:
                print("Wating Timeout waiting for bot message...")
                break
            if (self.driver.find_elements(By.XPATH, "//div[@data-visible='true' and contains(@class, 'Message_humanOptimisticFooter__zm1hu') and text()='Message failed to send.']")):
                self.reload()
            if time.time() - start_time > 120:
                self.kill_driver()
                raise Exception("Timeout waiting for bot message")
            time.sleep(1)

    @handle_errors
    def send_message_as_file(self, message):
        filename_length = secrets.randbelow(8) + 9
        filename = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(filename_length))

        [os.remove(i) for i in glob.glob(".cache/*.txt")]

        os.makedirs(".cache", exist_ok=True)
        txt_file_path = os.path.join(".cache", f"{filename}.txt")
        open(txt_file_path, 'w', encoding='utf-8').write(message)
        absolute_path = os.path.abspath(txt_file_path)

        file_input = self.driver.find_element(By.CLASS_NAME, 'ChatMessageFileInputButton_input__szx6_')
        file_input.send_keys(absolute_path)
        
        text_area = self.driver.find_element(By.CLASS_NAME, "GrowingTextArea_textArea__eadlu")
        text_area.send_keys(config.get("instruction", "-"))
        text_area.send_keys(Keys.RETURN)
    
    @handle_errors
    def send_message_as_text(self, message):
        text_area = self.driver.find_element(By.CLASS_NAME, "GrowingTextArea_textArea__eadlu")
        for part in message.split('\n'):
            text_area.send_keys(part)
            text_area.send_keys(Keys.SHIFT,Keys.ENTER)
           
        #message = message.replace("\n", " ")
        #text_area.send_keys(message)
        text_area.send_keys(Keys.RETURN)


    @handle_errors
    def clear_context(self):
        clear_button = self.driver.find_element(By.CLASS_NAME, "ChatBreakButton_button__EihE0")
        clear_button.click()

    @handle_errors
    def is_generating(self):
        stop_button_elements = self.driver.find_elements(By.CLASS_NAME, "ChatStopMessageButton_stopButton__LWNj6")
        return len(stop_button_elements) > 0
    
    @handle_errors
    def get_suggestions(self):
        suggestions_container = self.driver.find_elements(By.CLASS_NAME, "ChatMessageSuggestedReplies_suggestedRepliesContainer__JgW12")
        if not suggestions_container:
            return []
        suggestion_buttons = suggestions_container[0].find_elements(By.TAG_NAME, "button")
        return [button.text for button in suggestion_buttons]
    
    @handle_errors
    def delete_latest_message(self, bot = True):
        if (bot):
            messages = self.driver.find_elements(By.XPATH, '//div[contains(@class, "Message_botMessageBubble__CPGMI")]')
        else:
            messages = self.driver.find_elements(By.XPATH, '//div[contains(@class, "Message_humanMessageBubble__Nld4j")]')
        if (len(messages) == 0):
            return
        latest_message = messages[-1]
        self.driver.execute_script('arguments[0].scrollIntoView();',latest_message)
        time.sleep(2)
        ActionChains(self.driver).context_click(latest_message).perform()
        delete_button = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located(((By.XPATH, "//button[starts-with(@class, 'DropdownMenuItem_item__nYv_0') and contains(., 'Delete...')]"))))
        ActionChains(self.driver).move_to_element(delete_button).click().perform()
        confirm1_button = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".Button_buttonBase__0QP_m.Button_danger__zI3OH")))
        ActionChains(self.driver).move_to_element(confirm1_button).click().perform()
        confirm2_button = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located(((By.XPATH, "//button[@class='Button_buttonBase__0QP_m Button_danger__zI3OH']"))))
        ActionChains(self.driver).move_to_element(confirm2_button).click().perform()

  
    
    @handle_errors
    def reload(self):
        self.driver.refresh()

    def kill_driver(self):
        if hasattr(self, "driver"):
            self.driver.quit()

    def get_driver(self):
        if hasattr(self, "driver"):
            return self.driver

    def __del__(self):
        if hasattr(self, "driver"):
            self.kill_driver()

    
