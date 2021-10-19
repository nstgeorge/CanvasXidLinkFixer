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

LOGIN_TIMEOUT = 120
REFRESH_TIMEOUT = 600
BASE_URL = "https://boisestatecanvas.instructure.com"

##
#
#   This file contains the logic for fixing "xid" links in Canvas courses caused by Blackboard imports.
#   It uses Selenium to interact with the Canvas UI, with some BeautifulSoup usage when better served.
#   I apologize in advance if you're looking at this code, it is a bit hacky in places.
#   Nate St. George, LTS
#
##


class XIDException(Exception):
    """General exception type encountered when handling courses."""

    def __init__(self, message, caused_by=None):
        self.message = message
        self.caused_by = caused_by

    def __str__(self):
        return self.message

    def get_cause(self):
        return self.caused_by


def exists_css_selector(element: webdriver.remote, selector):
    """Return true if the given css selector exists on the page, false otherwise."""
    try:
        element.find_element(By.CSS_SELECTOR, selector)
    except NoSuchElementException:
        return False
    return True


def get_course_link(course_id):
    """Returns the course link for a given course ID."""
    return BASE_URL + "/courses/" + course_id


class XIDFixer:
    """Main class for fixing XID links."""

    def __init__(self, driver):
        self.__driver = driver

    def __replace_xid_in_tinymce(self, tinymce):
        """Replace all xid links in the provided tinymce context."""

        tinymce.click()

        original_text = self.__driver.execute_script("return tinyMCE.activeEditor.getContent()")

        soup = bs(original_text, "html.parser")
        try:
            images = [img for img in soup.find_all("img") if "xid" in (img["src"] or "")]
        except KeyError:
            print("Image without source found. That's weird.")
            images = []

        # Clear the editor's content (we will replace it later)
        if len(images) > 0:
            self.__driver.execute_script("tinyMCE.activeEditor.setContent('')")

        for image in images:
            image_name = image["src"].split("/")[-1]
            print(image_name)

            def after_course_images(driver):
                ui.WebDriverWait(driver, 10).until(
                    lambda d: d.find_element(By.CSS_SELECTOR, "div[title='Course Images']")).click()

                wait = ui.WebDriverWait(driver, 10)
                search = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "input[placeholder='Search']"))
                search.send_keys(image_name)

                time.sleep(1)  # Wait 1 second for image results to update

                # Find most relevant image with the xid provided
                try:
                    results = wait.until(lambda d: self.__wait_for_search_results())
                except TimeoutException as e:
                    raise XIDException("Failed to find image {}.".format(image_name), e)
                else:
                    for result in results.find_elements(By.TAG_NAME, "button"):
                        try:
                            if image_name in result.find_element(By.TAG_NAME, "img").get_attribute("alt"):
                                result.click()
                                break
                        except NoSuchElementException as e:
                            raise XIDException(
                                "The xid image {} does not appear to have been uploaded.".format(image_name), e)

                # Copy image source and clear tinyMCE
                image_source = driver.execute_script("return tinyMCE.activeEditor.getContent()")
                image_soup = bs(image_source, "html.parser")

                image.replaceWith(image_soup)

                driver.execute_script(
                    "tinyMCE.activeEditor.setContent('{}')".format(str(soup).replace("\n", "").replace("'", "\\'")))
                print("Content replaced")

            self.__open_course_images_in_rte(after_course_images)

    def __wait_for_search_results(self):
        """Wait for image search results to appear."""
        container = self.__driver.find_element(By.CSS_SELECTOR,
                                               "div[data-testid='instructure_links-ImagesPanel']").find_element(
            By.CSS_SELECTOR, "span")
        if exists_css_selector(container, "div"):
            return container
        return False

    def __open_course_images_in_rte(self, callback):
        """Perform a string of key actions that will open the Course Images button in tinyMCE."""
        command_key = Keys.COMMAND if platform == "darwin" else Keys.CONTROL
        ActionChains(self.__driver).key_down(command_key).key_down(Keys.SHIFT) \
            .send_keys("f") \
            .key_up(command_key).key_up(Keys.SHIFT).perform()  # Enter fullscreen
        ui.WebDriverWait(self.__driver, 10).until(lambda driver: driver.find_element(By.CLASS_NAME, "tox-fullscreen"))
        ActionChains(self.__driver).key_down(Keys.ALT).send_keys(Keys.F10).key_up(
            Keys.ALT).perform()  # Focus on toolbar
        ActionChains(self.__driver).send_keys(Keys.TAB, Keys.TAB, Keys.ARROW_RIGHT).perform()  # Go to Images
        ActionChains(self.__driver).key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(
            Keys.SHIFT).perform()  # Open dropdown
        callback()  # Run callback
        ActionChains(self.__driver).send_keys(Keys.ESCAPE, Keys.ESCAPE).perform()  # Exit fullscreen

    def __go_to_course_link_validator(self):
        """Navigate to course link validation page"""
        settings_link = ui.WebDriverWait(self.__driver, LOGIN_TIMEOUT) \
            .until(lambda d: d.find_element(By.LINK_TEXT, "Settings"))
        settings_link.click()
        self.__driver.find_element(By.PARTIAL_LINK_TEXT, "Validate Links in Content").click()

    def __open_in_new_tab(self, link):
        """Opens the given link in a new tab."""
        ActionChains(self.__driver).key_down(Keys.CONTROL).click(link).key_up(Keys.CONTROL).perform()

    def __click_at(self, element, x, y):
        """Click on an element at the given coordinates within that element."""
        ActionChains(self.__driver).move_to_element_with_offset(element, x, y).click().perform()

    def __hover(self, element):
        """Hover over the given element.
        Note that this code attempts two different hover methods.
        This is because ActionChains hover is not as reliable as JS."""
        self.__driver.execute_script("arguments[0].scrollIntoView();", element)
        ActionChains(self.__driver).move_to_element(element).perform()

    def __hover_and_click(self, hover_element, click_element):
        """Hover over the given element and click on another (or the same) element."""
        self.__hover(hover_element)
        time.sleep(0.1)
        ActionChains(self.__driver).click(click_element).perform()

    def __find_elements_by_text(self, text, element=None):
        """Helper function that returns any elements that contain the given text.
        If `element` is provided, only searches within that element."""
        return (element if element else self.__driver).find_elements(By.XPATH,
                                                                     ".//*[contains(text(), '{}')]".format(text))

    def __handle_assessment_question_pool(self, start_index=0):
        """Handle an assessment question with one or more broken xid links.
        Note that assessment question links actually navigate to question pools and not individual questions."""
        questions = [q for q in ui.WebDriverWait(self.__driver, 10).until(
            lambda d: d.find_elements(By.CLASS_NAME, "question_holder")) if
                     "display: none" not in q.get_attribute("style")]
        print("Questions: {}".format(len(questions)))

        self.__driver.execute_script("window.scrollTo(0,0)")

        for q_index, question in enumerate(questions):
            if q_index < start_index:
                return
            print("Fixing question {} -------------------- ".format(q_index + 1))
            try:
                self.__fix_single_question(question)
            except XIDException as e:
                print("ERROR IN QUESTION: {}".format(e.message))
                continue

    def __fix_single_question(self, question):
        """Fix a single assessment question."""
        hovered = False
        attempts = 0
        while not hovered and attempts < 500:
            try:
                self.__hover_and_click(question,
                                       question.find_element(By.CSS_SELECTOR, "a[class*=edit_question_link]"))
                hovered = True
            except (MoveTargetOutOfBoundsException, ElementNotInteractableException, NoSuchElementException):
                attempts += 1

        if attempts == 500:
            raise XIDException("Ran out of hover attempts")

        # Try to fix the question text
        wait = ui.WebDriverWait(self.__driver, 30)
        try:
            editors = wait.until(lambda d: d.find_elements(By.CLASS_NAME, "tox-edit-area__iframe"))
        except TimeoutException as e:
            raise XIDException("Unable to find editor for this question.", e)

        tinymce = None
        for i, editor in enumerate(editors):
            if editor.get_attribute("id") != "quiz_description_ifr":
                print("Choosing editor {}/{}".format(i + 1, len(editors)))
                tinymce = editor
                break

        self.__replace_xid_in_tinymce(tinymce)

        # Find broken links in answers
        for answer in self.__driver.find_element(By.CLASS_NAME, "form_answers").find_elements(By.CLASS_NAME, "answer"):
            if any("xid" in i.get_attribute("src") for i in answer.find_elements(By.TAG_NAME, "img")):
                mark_correct = "correct_answer" in answer.get_attribute("class")
                ui.WebDriverWait(self.__driver, 5).until((EC.visibility_of(answer)))
                self.__driver.execute_script("arguments[0].setAttribute('class', 'answer hover')", answer)
                try:
                    ui.WebDriverWait(answer, 5).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, "a[class='edit_html']")).click()
                    tinymce = ui.WebDriverWait(answer, 30).until(
                        lambda d: d.find_element(By.CLASS_NAME, "tox-edit-area__iframe")
                    )
                except (ElementNotInteractableException, TimeoutException) as e:
                    raise XIDException("Failed to click on answer.", e)
                except ElementClickInterceptedException:
                    # Handle pop-up that occurs when students have already taken a quiz.
                    # We aren't changing which answer is correct,
                    # just re-pressing the button, so it's okay to skip regrading.
                    # Still, might be good to let the professor know.
                    print("Element has been covered. Attempting to clear screen.")
                    widget = self.__driver.find_element(By.CLASS_NAME, "ui-widget")
                    ui.WebDriverWait(widget, 5).until(
                        lambda d: self.__find_elements_by_text("Update question without regrading")[0]).click()
                    self.__find_elements_by_text("Update", element=widget)[0].click()
                    ui.WebDriverWait(answer, 5).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, "a[class='edit_html']")).click()
                    tinymce = ui.WebDriverWait(answer, 30).until(
                        lambda d: d.find_element(By.CLASS_NAME, "tox-edit-area__iframe")
                    )

                self.__replace_xid_in_tinymce(tinymce)
                if mark_correct:
                    answer.find_element(By.CLASS_NAME, "select_answer_link").click()

        self.__driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

        # Check for errors
        try:
            ui.WebDriverWait(self.__driver, 2).until(lambda d: d.find_element(By.CLASS_NAME, "errorBox"))
        except (TimeoutException, NoSuchElementException):
            pass
        else:
            print("Error message detected. It is likely that this edit failed to save.")

    def __handle_quiz_question(self):
        """Handle a quiz question. Most of the flow is shared with assessment question pools."""
        ui.WebDriverWait(self.__driver, 10).until(
            lambda d: self.__driver.find_element(By.CLASS_NAME, "edit_assignment_link")).click()
        self.__driver.find_element(By.LINK_TEXT, "Questions").click()
        self.__handle_assessment_question_pool()

    def __handle_page(self):
        """Handle a page with an xid link."""
        ui.WebDriverWait(self.__driver, 10).until(
            lambda d: d.find_element(By.CLASS_NAME, "edit-wiki")).click()
        tinymce = ui.WebDriverWait(self.__driver, 10).until(
            lambda d: d.find_element(By.CLASS_NAME, "tox-edit-area__iframe")
        )
        self.__replace_xid_in_tinymce(tinymce)
        self.__driver.find_element(By.CSS_SELECTOR, "button[class*=submit]").click()

    def __handle_assignment(self):
        """Handle an assignment with an xid link."""
        ui.WebDriverWait(self.__driver, 10).until(
            lambda d: d.find_element(By.CLASS_NAME, "edit_assignment_link")).click()
        tinymce = ui.WebDriverWait(self.__driver, 10).until(
            lambda d: d.find_element(By.CLASS_NAME, "tox-edit-area__iframe")
        )
        self.__replace_xid_in_tinymce(tinymce)
        self.__driver.find_element(By.CSS_SELECTOR, "button[class*=submit]").click()

    def __handle_discussion(self):
        """Handle a discussion topic with an xid link. Very similar to page handling."""
        ui.WebDriverWait(self.__driver, 10).until(lambda d: self.__driver.find_element(By.CLASS_NAME, "edit-btn")).click()
        tinymce = ui.WebDriverWait(self.__driver, 10).until(
            lambda d: self.__driver.find_element(By.CLASS_NAME, "tox-edit-area__iframe")
        )
        self.__replace_xid_in_tinymce(tinymce)
        self.__driver.find_element(By.CSS_SELECTOR, "button[class*=submit]").click()

    def do_course(self, course, username, password, revalidate_links=False):
        """Fix all XID links within the given course. Expects valid Boise State identification.
        This is the only public function in the class.
        returns a tuple: `failed_items, attempted_items, err`
        If an error occurs, `err` will have a very brief description that the UI can expand on.
        """
        self.__driver.get(get_course_link(course) if course.isnumeric() else course)

        if "Log In" in self.__driver.title:
            self.__driver.find_element(By.XPATH,
                                       ".//img[contains(@alt, 'Boise State Logo')]/following-sibling::ion-button")\
                .click()

            username_input = ui.WebDriverWait(self.__driver, 10).until(
                lambda d: d.find_element(By.ID, "userNameInput")
            )
            username_input.send_keys(username)
            self.__driver.find_element(By.ID, "passwordInput").send_keys(password)
            self.__driver.find_element(By.ID, "submitButton").click()

            login_fail = ui.WebDriverWait(self.__driver, 5).until(lambda d: exists_css_selector(d, ".login_error"))
            if login_fail:
                return 0, 0, "login_fail"

        self.__go_to_course_link_validator()

        # Find results
        results = self.__driver.find_elements(By.CLASS_NAME, "result")
        if len(results) == 0 or revalidate_links:
            print("Refreshing broken links. This request will time out in 10 minutes.")
            wait_links = ui.WebDriverWait(self.__driver, REFRESH_TIMEOUT)
            try:
                self.__driver.find_element(By.PARTIAL_LINK_TEXT, "Link Validation").click()
            except NoSuchElementException:
                print("Unable to refresh link validation: element not found")

            results = wait_links.until(lambda driver: driver.find_elements(By.CLASS_NAME, "result"))

        # Filter results to only those with "xid" in the link
        xid_items = [r for r in results if len(r.find_elements(By.PARTIAL_LINK_TEXT, "xid")) != 0]

        print("{} xid items found. Beginning fixes...".format(len(xid_items)))

        main_window = self.__driver.current_window_handle
        fixed_banks = []
        failed_items = 0

        # Detect item type and send to proper function.
        # Normally I would navigate to the correct element and do a switch on the text,
        # but Canvas uses non-human-readable class names for these elements and I don't want the system to break
        # if the class names are nondeterministic, which seems likely.
        for item in xid_items:
            handle_count = len(self.__driver.window_handles)
            try:
                url = item.find_element(By.TAG_NAME, "h2").find_element(By.TAG_NAME, "a").get_attribute("href")
                url = url.split("#")[0]
                if url in fixed_banks:
                    print("This question has already been fixed "
                          "because it belongs to the same bank as a previous question.")
                    continue
                fixed_banks.append(url)
            except Exception:
                failed_items += 1
                continue
            # driver.execute_script("window.open('{}', '_blank')".format(url))

            try:
                # Wait until the new tab is open
                wait = ui.WebDriverWait(self.__driver, 10)

                # Handle different types of pages
                if len(self.__find_elements_by_text("Assessment Question", element=item)) != 0:
                    self.__driver.switch_to.new_window("tab")
                    wait.until(lambda d: len(self.__driver.window_handles) != handle_count)
                    self.__driver.get(url)
                    self.__handle_assessment_question_pool()
                elif len(self.__find_elements_by_text("Quiz Question", element=item)) != 0:
                    self.__driver.switch_to.new_window("tab")
                    wait.until(lambda d: len(self.__driver.window_handles) != handle_count)
                    self.__driver.get(url)
                    self.__handle_quiz_question()
                elif len(self.__find_elements_by_text("Page", element=item)) != 0:
                    self.__driver.switch_to.new_window("tab")
                    wait.until(lambda d: len(self.__driver.window_handles) != handle_count)
                    self.__driver.get(url)
                    self.__handle_page()
                elif len(self.__find_elements_by_text("Assignment", element=item)) != 0:
                    self.__driver.switch_to.new_window("tab")
                    wait.until(lambda d: len(self.__driver.window_handles) != handle_count)
                    self.__driver.get(url)
                    self.__handle_assignment()
                elif len(self.__find_elements_by_text("Discussion", element=item)) != 0:
                    self.__driver.switch_to.new_window("tab")
                    wait.until(lambda d: len(self.__driver.window_handles) != handle_count)
                    self.__driver.get(url)
                    self.__handle_discussion()
                else:
                    print("Unrecognized page type!")
                    # open a new window so we don't close the main window.
                    self.__driver.switch_to.new_window("tab")
                    wait.until(lambda d: len(self.__driver.window_handles) != handle_count)

                self.__driver.close()
                self.__driver.switch_to.window(main_window)
            except Exception:
                failed_items += 1

        return failed_items, len(xid_items)
