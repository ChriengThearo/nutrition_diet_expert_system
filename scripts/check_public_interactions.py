"""Small browser smoke check for the four intended public pages.

Run with a local Flask server and Selenium, for example:
    uv run --with selenium python scripts/check_public_interactions.py http://127.0.0.1:5017
"""

import json
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


def check(origin):
    options = Options()
    options.add_argument("--headless=new")
    options.page_load_strategy = "eager"
    driver = webdriver.Chrome(options=options)
    results = []
    try:
        def click_center(selector):
            element = driver.find_element(By.ID, selector)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'})", element)
            time.sleep(0.2)
            element.click()

        for width in (320, 390):
            driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                "width": width, "height": 844, "deviceScaleFactor": 1, "mobile": True,
            })
            for path, lang in (("/", "en"), ("/km/", "km"),
                               ("/bmi", "en"), ("/km/bmi", "km")):
                driver.get(origin.rstrip("/") + path)
                time.sleep(1)
                state = driver.execute_script("""
                    return {lang: document.documentElement.lang,
                      viewport: document.documentElement.clientWidth,
                      width: document.documentElement.scrollWidth,
                      h1: document.querySelectorAll('h1').length};
                """)
                assert state["lang"] == lang, (path, state)
                assert state["h1"] == 1, (path, state)
                assert state["width"] <= state["viewport"], (path, width, state)
                results.append({"width": width, "path": path, **state})

        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True,
        })
        for path, target in (("/", "/km/"), ("/km/", "/")):
            driver.get(origin.rstrip("/") + path)
            WebDriverWait(driver, 15).until(lambda d: d.execute_script("return typeof bootstrap !== 'undefined'"))
            driver.find_element(By.CSS_SELECTOR, ".navbar-toggler").click()
            WebDriverWait(driver, 5).until(lambda d: d.find_element(By.ID, "homeLanguageModeDropdown").is_displayed())
            driver.find_element(By.ID, "homeLanguageModeDropdown").click()
            link = next(link for link in driver.find_elements(By.CSS_SELECTOR, f'a[href="{target}"]')
                        if link.is_displayed())
            link.click()
            assert driver.current_url.endswith(target), (path, driver.current_url)

        for path in ("/bmi", "/km/bmi"):
            driver.get(origin.rstrip("/") + path)
            WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState === 'complete'"))
            for field, value in (("weight", "70"), ("height", "175"), ("age", "20")):
                driver.find_element(By.ID, field).send_keys(value)
            click_center("btnCalculate")
            assert "22.9" in driver.find_element(By.ID, "resultBody").text
            click_center("btnSave")
            history = driver.execute_script("return JSON.parse(localStorage.getItem('bmi_results'))")
            assert history[0]["bmi"] == 22.9 and history[0]["age"] == 20
            driver.find_element(By.ID, "height").clear()
            driver.find_element(By.ID, "height").send_keys("100")
            for weight, category in (("18.49", "underweight"), ("18.5", "normal"),
                                     ("24.99", "normal"), ("25", "overweight"),
                                     ("29.99", "overweight"), ("30", "obese")):
                field = driver.find_element(By.ID, "weight")
                field.clear()
                field.send_keys(weight)
                click_center("btnCalculate")
                actual = driver.find_element(By.CSS_SELECTOR, ".gauge-category").get_attribute("class")
                assert "category-" + category in actual, (path, weight, actual)
            driver.find_element(By.ID, "age").clear()
            driver.find_element(By.ID, "age").send_keys("19")
            click_center("btnCalculate")
            alert = driver.switch_to.alert
            assert alert.text
            alert.accept()
            click_center("btnClear")
            assert "22.9" not in driver.find_element(By.ID, "resultBody").text
        return {"layout": results, "languageSwitches": 2,
                "adultCalculatorInteractions": 2}
    finally:
        driver.quit()


if __name__ == "__main__":
    print(json.dumps(check(sys.argv[1])))
