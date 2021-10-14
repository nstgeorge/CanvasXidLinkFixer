import contextlib
import time
from sys import platform

from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException, \
    MoveTargetOutOfBoundsException, ElementNotInteractableException, ElementClickInterceptedException
import selenium.webdriver.support.ui as ui
from bs4 import BeautifulSoup as bs
import argparse

import streamlit as st

LOGIN_TIMEOUT = 120
REFRESH_TIMEOUT = 600
BASE_URL = "https://boisestatecanvas.instructure.com"


class XIDException(Exception):
    def __init__(self, message, caused_by=None):
        self.message = message
        self.caused_by = caused_by

    def __str__(self):
        return self.message

    def get_cause(self):
        return self.caused_by


def replace_xid_in_tinymce(driver, tinymce):
    """Replace all xid links in the provided tinymce context."""

    tinymce.click()

    original_text = driver.execute_script("return tinyMCE.activeEditor.getContent()")

    soup = bs(original_text, "html.parser")
    try:
        images = [img for img in soup.find_all("img") if "xid" in (img["src"] or "")]
    except KeyError:
        print("Image without source found. That's weird.")
        images = []

    # Clear the editor's content (we will replace it later)
    if len(images) > 0:
        driver.execute_script("tinyMCE.activeEditor.setContent('')")

    for image in images:
        image_name = image["src"].split("/")[-1]
        print(image_name)

        # ui.WebDriverWait(driver, 120).until(lambda driver: driver.find_element_by_css_selector("div[title='Images']"))

        def after_course_images(driver):
            ui.WebDriverWait(driver, 10).until(
                lambda driver: driver.find_element(By.CSS_SELECTOR, "div[title='Course Images']")).click()

            wait = ui.WebDriverWait(driver, 10)
            search = wait.until(lambda driver: driver.find_element(By.CSS_SELECTOR, "input[placeholder='Search']"))
            search.send_keys(image_name)

            time.sleep(1)  # Wait 1 second for image results to update

            # Find most relevant image with the xid provided
            try:
                results = wait.until(lambda driver: wait_for_search_results(driver))
            except TimeoutException as e:
                raise XIDException("Failed to find image {}.".format(image_name), e)
            else:
                for result in results.find_elements(By.TAG_NAME, "button"):
                    try:
                        if image_name in result.find_element(By.TAG_NAME, "img").get_attribute("alt"):
                            result.click()
                            break
                    except NoSuchElementException as e:
                        raise XIDException("The xid image {} does not appear to have been uploaded.".format(image_name), e)

            # Copy image source and clear tinyMCE
            image_source = driver.execute_script("return tinyMCE.activeEditor.getContent()")
            image_soup = bs(image_source, "html.parser")

            image.replaceWith(image_soup)

            driver.execute_script(
                "tinyMCE.activeEditor.setContent('{}')".format(str(soup).replace("\n", "").replace("'", "\\'")))
            print("Content replaced")

        open_course_images_in_rte(driver, after_course_images)


def wait_for_search_results(driver):
    """Wait for image search results to appear."""
    container = driver.find_element(By.CSS_SELECTOR, "div[data-testid='instructure_links-ImagesPanel']").find_element(
        By.CSS_SELECTOR, "span")
    if exists_css_selector(container, "div"):
        return container
    return False


def open_course_images_in_rte(driver, callback):
    """Perform a string of key actions that will open the Course Images button in tinyMCE."""
    command_key = Keys.COMMAND if platform == "darwin" else Keys.CONTROL
    ActionChains(driver).key_down(command_key).key_down(Keys.SHIFT) \
        .send_keys("f") \
        .key_up(command_key).key_up(Keys.SHIFT).perform()  # Enter fullscreen
    ui.WebDriverWait(driver, 10).until(lambda driver: driver.find_element(By.CLASS_NAME, "tox-fullscreen"))
    ActionChains(driver).key_down(Keys.ALT).send_keys(Keys.F10).key_up(Keys.ALT).perform()  # Focus on toolbar
    ActionChains(driver).send_keys(Keys.TAB, Keys.TAB, Keys.ARROW_RIGHT).perform()  # Go to Images
    ActionChains(driver).key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(Keys.SHIFT).perform()  # Open dropdown
    callback(driver)  # Run callback
    ActionChains(driver).send_keys(Keys.ESCAPE, Keys.ESCAPE).perform()  # Exit fullscreen


def go_to_course_link_validator(driver, wait=None):
    """Navigate to course link validation page"""
    if wait is not None:
        settings_link = wait.until(lambda driver: driver.find_element(By.LINK_TEXT, "Settings"))
    else:
        settings_link = driver.find_element(By.PARTIAL_LINK_TEXT, "Settings")
    settings_link.click()
    driver.find_element(By.PARTIAL_LINK_TEXT, "Validate Links in Content").click()


def exists_css_selector(driver, selector):
    """Return true if the given css selector exists on the page, false otherwise."""
    try:
        driver.find_element(By.CSS_SELECTOR, selector)
    except NoSuchElementException:
        return False
    return True


def get_course_link(id):
    """Returns the course link for a given course ID."""
    return BASE_URL + "/courses/" + id


def open_in_new_tab(driver, link):
    """Opens the given link in a new tab."""
    ActionChains(driver).key_down(Keys.CONTROL).click(link).key_up(Keys.CONTROL).perform()


def click_at(driver, element, x, y):
    """Click on an element at the given coordinates within that element."""
    ActionChains(driver).move_to_element_with_offset(element, x, y).click().perform()


def hover(driver, element):
    """Hover over the given element."""
    ActionChains(driver).move_to_element(element).perform()


def hover_and_click(driver, hover_element, click_element):
    """Hover over the given element and click.
    Note that this code attempts two different hover methods. This is because ActionChains hover is not as reliable."""
    driver.execute_script("arguments[0].scrollIntoView();", hover_element)
    ActionChains(driver).move_to_element(hover_element).perform()
    time.sleep(0.1)
    ActionChains(driver).click(click_element).perform()


def find_elements_by_text(driver, text):
    """Helper function that returns any elements that contain the given text."""
    return driver.find_elements(By.XPATH, ".//*[contains(text(), '{}')]".format(text))


def handle_assessment_question_pool(driver, start_index=0):
    """Handle an assessment question with one or more broken xid links.
    Note that assessment question links actually navigate to question pools and not individual questions."""
    questions = [q for q in ui.WebDriverWait(driver, 10).until(
        lambda driver: driver.find_elements(By.CLASS_NAME, "question_holder")) if
                 "display: none" not in q.get_attribute("style")]
    print("Questions: {}".format(len(questions)))

    driver.execute_script("window.scrollTo(0,0)")

    for q_index, question in enumerate(questions):
        if q_index < start_index:
            return
        print("Fixing question {} -------------------- ".format(q_index + 1))
        try:
            fix_single_question(question, driver)
        except XIDException as e:
            print("ERROR IN QUESTION: {}".format(e.message))
            continue


def fix_single_question(question, driver):
    hovered = False
    attempts = 0
    while not hovered and attempts < 500:
        try:
            hover_and_click(driver, question,
                            question.find_element(By.CSS_SELECTOR, "a[class*=edit_question_link]"))
            hovered = True
        except (MoveTargetOutOfBoundsException, ElementNotInteractableException, NoSuchElementException):
            attempts += 1

    if attempts == 500:
        raise XIDException("Ran out of hover attempts")

    # Try to fix the question text
    wait = ui.WebDriverWait(driver, 30)
    try:
        editors = wait.until(lambda driver: driver.find_elements(By.CLASS_NAME, "tox-edit-area__iframe"))
    except TimeoutException as e:
        raise XIDException("Unable to find editor for this question.", e)
    print("{} editors available".format(len(editors)))
    for i, editor in enumerate(editors):
        if editor.get_attribute("id") != "quiz_description_ifr":
            print("Choosing editor {}/{}".format(i + 1, len(editors)))
            tinymce = editor
            break

    print("Replacing xid links")

    replace_xid_in_tinymce(driver, tinymce)

    print("Done replacing, checking answers")

    # Find broken links in answers
    for answer in driver.find_element(By.CLASS_NAME, "form_answers").find_elements(By.CLASS_NAME, "answer"):
        if any("xid" in i.get_attribute("src") for i in answer.find_elements(By.TAG_NAME, "img")):
            mark_correct = "correct_answer" in answer.get_attribute("class")
            ui.WebDriverWait(driver, 5).until((EC.visibility_of(answer)))
            # driver.execute_script("arguments[0].scrollIntoView();", answer.find_element_by_class_name("question_actions"))
            driver.execute_script("arguments[0].setAttribute('class', 'answer hover')", answer)
            try:
                ui.WebDriverWait(driver, 5).until(
                    lambda answer: answer.find_element(By.CSS_SELECTOR, "a[class='edit_html']")).click()
                tinymce = ui.WebDriverWait(answer, 30).until(
                    lambda driver: driver.find_element(By.CLASS_NAME, "tox-edit-area__iframe")
                )
            except (ElementNotInteractableException, TimeoutException) as e:
                raise XIDException("Failed to click on answer.", e)
            except ElementClickInterceptedException as e:
                # Handle pop-up that occurs when students have already taken a quiz.
                # We aren't changing which answer is correct (just re-pressing the button, so it's okay to skip regrading.
                # Still, might be good to let the professor know.
                print("Element has been covered. Attempting to clear screen.")
                widget = driver.find_element(By.CLASS_NAME, "ui-widget")
                ui.WebDriverWait(widget, 5).until(
                    lambda driver: find_elements_by_text(driver, "Update question without regrading")[0]).click()
                find_elements_by_text(widget, "Update")[0].click()
                ui.WebDriverWait(driver, 5).until(
                    lambda answer: answer.find_element(By.CSS_SELECTOR, "a[class='edit_html']")).click()
                tinymce = ui.WebDriverWait(answer, 30).until(
                    lambda driver: driver.find_element(By.CLASS_NAME, "tox-edit-area__iframe")
                )
                continue
            # hover_and_click(driver, answer, ui.WebDriverWait(driver, 5).until(lambda answer: answer.find_element_by_css_selector("a[class='edit_html']")))
            replace_xid_in_tinymce(driver, tinymce)
            if mark_correct:
                answer.find_element(By.CLASS_NAME, "select_answer_link").click()

    print("Submitting")
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

    # Check for errors
    try:
        ui.WebDriverWait(driver, 2).until(lambda driver: driver.find_element(By.CLASS_NAME, "errorBox"))
    except (TimeoutException, NoSuchElementException):
        pass
    else:
        print("Error message detected. It is likely that this edit failed to save.")


def handle_quiz_question(driver):
    """Handle a quiz question. Most of the flow is shared with assessment question pools."""
    ui.WebDriverWait(driver, 10).until(
        lambda driver: driver.find_element(By.CLASS_NAME, "edit_assignment_link")).click()
    driver.find_element(By.LINK_TEXT, "Questions").click()
    handle_assessment_question_pool(driver)


def handle_page(driver):
    """Handle a page with an xid link."""
    ui.WebDriverWait(driver, 10).until(lambda driver: driver.find_element(By.CLASS_NAME, "edit-wiki")).click()
    tinymce = ui.WebDriverWait(driver, 10).until(
        lambda driver: driver.find_element(By.CLASS_NAME, "tox-edit-area__iframe")
    )
    replace_xid_in_tinymce(driver, tinymce)
    driver.find_element(By.CSS_SELECTOR, "button[class*=submit]").click()


def handle_discussion(driver):
    """Handle a discussion topic with an xid link. Very similar to page handling."""
    ui.WebDriverWait(driver, 10).until(lambda driver: driver.find_element(By.CLASS_NAME, "edit-btn")).click()
    tinymce = ui.WebDriverWait(driver, 10).until(
        lambda driver: driver.find_element(By.CLASS_NAME, "tox-edit-area__iframe")
    )
    replace_xid_in_tinymce(driver, tinymce)
    driver.find_element(By.CSS_SELECTOR, "button[class*=submit]").click()

def build_ui(driver):
    """Create the Streamlit UI for the app."""
    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix broken \"xid\" links in a Canvas course.")
    parser.add_argument('--force-refresh-links',
                        dest="refresh",
                        default=False,
                        action="store_true",
                        help="If specified, the program will always refresh the broken "
                             "course links, even if it can find the list.")
    parser.add_argument('--is-chrome',
                        dest="chrome",
                        default=False,
                        action="store_true",
                        help="If specified, loads ChromeDriver instead of geckodriver.")
    parser.add_argument('-c', '--course', nargs="+", required=True,
                        help="Link(s) to the Canvas course(s) to modify.")

    args = parser.parse_args()
    browser = webdriver.Firefox() if not args.chrome else webdriver.Chrome()

    with contextlib.closing(browser) as driver:
        for course in args.course:
            print("Beginning course link fix on {}...".format(course))
            driver.get(get_course_link(course) if course.isnumeric() else course)

            if "Log In" in driver.title:
                print("Please log into your Boise State account to access this course. In {} seconds, this request will"
                      " time out.".format(LOGIN_TIMEOUT))
            wait = ui.WebDriverWait(driver, LOGIN_TIMEOUT)
            go_to_course_link_validator(driver, wait)

            # Find results
            results = driver.find_elements(By.CLASS_NAME, "result")
            if len(results) == 0 or args.refresh:
                print("Refreshing broken links. This request will time out in 10 minutes.")
                wait_links = ui.WebDriverWait(driver, REFRESH_TIMEOUT)
                try:
                    driver.find_element(By.PARTIAL_LINK_TEXT, "Link Validation").click()
                except NoSuchElementException:
                    print("Unable to refresh link validation: element not found")

                results = wait_links.until(lambda driver: driver.find_elements(By.CLASS_NAME, "result"))

            # Filter results to only those with "xid" in the link
            xid_items = [r for r in results if len(r.find_elements(By.PARTIAL_LINK_TEXT, "xid")) != 0]

            print("{} xid items found. Beginning fixes...".format(len(xid_items)))

            main_window = driver.current_window_handle
            fixed_banks = []
            failed_items = 0

            # Detect item type and send to proper function.
            # Normally I would navigate to the correct element and do a switch on the text,
            # but Canvas uses non-human-readable class names for these elements and I don't want the system to break
            # if the class names are nondeterministic, which seems likely.
            for item in xid_items:
                handle_count = len(driver.window_handles)
                try:
                    url = item.find_element(By.TAG_NAME, "h2").find_element(By.TAG_NAME, "a").get_attribute("href")
                    url = url.split("#")[0]
                    if url in fixed_banks:
                        print(
                            "This question has already been fixed because it belongs to the same bank as a previous question.")
                        continue
                    print(url)
                    fixed_banks.append(url)
                except Exception:
                    print("Unable to check this item against previously fixed banks. Attempting to fix.")

                # driver.execute_script("window.open('{}', '_blank')".format(url))

                try:
                    # Wait until the new tab is open
                    wait = ui.WebDriverWait(driver, 10)

                    # Handle different types of pages
                    if len(find_elements_by_text(item, "Assessment Question")) != 0:
                        # print(len(find_elements_by_text(item, "Assessment Question")))
                        # driver.switch_to.window(driver.window_handles[1])
                        driver.switch_to.new_window("tab")
                        wait.until(lambda driver: len(driver.window_handles) != handle_count)
                        driver.get(url)
                        handle_assessment_question_pool(driver)
                    elif len(find_elements_by_text(item, "Quiz Question")) != 0:
                        # driver.switch_to.window(driver.window_handles[1])
                        driver.switch_to.new_window("tab")
                        wait.until(lambda driver: len(driver.window_handles) != handle_count)
                        driver.get(url)
                        handle_quiz_question(driver)
                    elif len(find_elements_by_text(item, "Page")) != 0 or len(
                            find_elements_by_text(item, "Assignment")) != 0:
                        # driver.switch_to.window(driver.window_handles[1])
                        driver.switch_to.new_window("tab")
                        wait.until(lambda driver: len(driver.window_handles) != handle_count)
                        driver.get(url)
                        handle_page(driver)
                    elif len(find_elements_by_text(item, "Discussion")) != 0:
                        # driver.switch_to.window(driver.window_handles[1])
                        driver.switch_to.new_window("tab")
                        wait.until(lambda driver: len(driver.window_handles) != handle_count)
                        driver.get(url)
                        handle_discussion(driver)
                    else:
                        print("Unrecognized page type!")
                        # open a new window so we don't close the main window.
                        driver.switch_to.new_window("tab")
                        wait.until(lambda driver: len(driver.window_handles) != handle_count)

                    driver.close()
                    driver.switch_to.window(main_window)
                except Exception as e:
                    failed_items += 1
                    print("Item failed to be fixed. Error: {}".format(str(e)))
            print("Course complete.")

        print("Done.")
