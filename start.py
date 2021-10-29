import contextlib
import time
import datetime
import os

from selenium import webdriver
import streamlit as st
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

from fixer import XIDFixer

GOOGLE_CHROME_PATH = os.environ.get('GOOGLE_CHROME_BIN', "/app/.apt/usr/bin/google_chrome")

##
#
#   This file creates a web-based UI for the XID Fixer class using Streamlit.
#   It expects that Chrome and ChromeDriver are installed on the host machine.
#   Start this code by running `streamlit run start.py` after installing dependencies.
#   Nate St. George, LTS
#
##


def draw_sidebar():
    """Draw the sidebar based on the state of the program."""
    if "username" in st.session_state and "password" in st.session_state:
        st.sidebar.header("Authentication")
        st.sidebar.markdown("Logged in as **{}**".format(st.session_state.username))
        if st.sidebar.button("Log Out"):
            del st.session_state.username
            del st.session_state.password
            st.experimental_rerun()

    if "courses" in st.session_state:
        st.sidebar.header("Courses Queued")
        for c in st.session_state.courses:
            st.sidebar.markdown(c)

        if st.sidebar.button("Clear"):
            del st.session_state.courses
            st.experimental_rerun()


def get_item_fail_message(fail_type):
    """Returns a detailed fail message for a given fail type."""
    if fail_type == "already_fixed":
        return "Item has already been fixed because it's from the same pool as a previous question."
    else:
        return "Unknown reason."


def run_fix():
    start_time = time.time()
    options = Options()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.binary_location = GOOGLE_CHROME_PATH
    options.headless = True
    service = Service(ChromeDriverManager().install())
    browser = webdriver.Chrome(service=service, options=options)
    progress_container = btn_container.container()
    status = progress_container.empty()
    progress = progress_container.empty()
    course_status = progress_container.empty()

    err = None

    total_failed = 0
    total_attempted = 0
    total_items = 0

    with contextlib.closing(browser) as driver:
        xid_fix = XIDFixer(driver)
        for i, course in enumerate(st.session_state.courses):
            status.caption("Starting work on {}...".format(course))
            for msg, arg in xid_fix.do_course(course, st.session_state.username,
                                                              st.session_state.password, revalidate_links):
                if total_items != 0:
                    progress.progress(max(total_attempted / total_items, 1.0))
                else:
                    progress.progress(0)

                # Handle errors
                print(msg[:3])
                if msg[:3] == "err":
                    err = msg[4:]
                    print(err)
                # Handle other message types
                if msg == "waiting_for_duo":
                    course_status.caption("You should have received a Duo push. Please approve the login request. "
                                          "Note: The location shown on the push will not be your real location.")
                if msg == "duo_success":
                    course_status.caption("Duo approved, beginning course fix...")
                if msg == "total_items":
                    total_items = arg
                if msg == "item_failed":
                    total_failed += 1
                    total_attempted += 1
                    course_status.caption("Previous item failed to fix: {}".format(get_item_fail_message(arg)))
                if msg == "item_success":
                    course_status.caption("Previous item succeeded")
                    total_attempted += 1
                if msg == "done":
                    course_status.caption("Course complete!")

                status.markdown("**Course {} ({}/{}):** **{}** of **{}** failed so far, **{}** total items".format(
                    course,
                    i + 1,
                    len(st.session_state.courses),
                    total_failed,
                    total_attempted,
                    total_items
                ))

            if err is not None:
                if err == "login_fail":
                    alert.error("Failed to log into your Boise State account. Please log out "
                                "and re-enter your information.")
                elif err == "login_not_interactable":
                    alert.error("Unable to interact with login page. This is usually fixed with a rerun.")
                elif err == "duo_fail":
                    alert.error("The Duo request has timed out. "
                                "If you didn't receive a push notification, make sure your Duo account is set up "
                                "to automatically send push notifications instead of asking for an authentication "
                                "method.")
                elif err == "timeout_fail":
                    alert.error("The course link validation has taken too long. "
                                "It is still running, so try rerunning the course.")
                elif err == "course_dne":
                    alert.error("The course {} does not exist, skipping.".format(course))
                else:
                    alert.error("An unknown error occurred. Code: {}. Stopping.".format(err))
                break

    if not err:
        progress.progress(100)
        status.caption("Done!")
        alert.success("Fix complete for all courses! {} of {} attempted items were successful. Time: {}.".format(
            total_attempted - total_failed, total_attempted,
            datetime.timedelta(seconds=time.time() - start_time)
        ))

    time.sleep(3)
    if btn_container.button("Rerun"):
        run_fix()


if __name__ == "__main__":

    alert = st.empty()

    if "username" not in st.session_state or "password" not in st.session_state:
        # Show login screen
        with st.form(key="login_form"):
            st.title("Sign in to Your Boise State Account")
            st.caption("This form saves your Boise State login information locally, "
                       "then submits it whenever a login is prompted. This is not a Boise State login page, "
                       "and does not check if your information is valid.")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In")

            if submitted:
                st.session_state.username = username
                st.session_state.password = password
                st.experimental_rerun()

    elif "courses" not in st.session_state:
        draw_sidebar()

        # Show course selection screen
        with st.form(key="course_form"):
            st.title("Add Courses")
            st.caption("You can either put the full course URL or just the course ID, like \"1111.\" "
                       "Each course must be separated by whitespace (either space or each on their own line), "
                       "do not use commas.")
            courses = st.text_area("Courses")
            submitted = st.form_submit_button("Continue")

            if submitted:
                st.session_state.courses = courses.split()
                st.experimental_rerun()
    else:
        draw_sidebar()

        st.title("Course Fix")
        st.markdown("Take a second to verify that your course links/IDs are correct. "
                    "Then, when you're ready, press the **Start** button below. "
                    "Alternatively, you can clear the course list in the sidebar and try again.")

        st.markdown("You will likely be asked to complete Duo authentication on your device. "
                    "**Please ensure that your Duo is set to [automatically send push requests.]"
                    "(https://www.boisestate.edu/oit-myboisestate/customize-your-duo-security-preferences/)**")

        btn_container = st.empty()
        col1, col2 = btn_container.columns(2)
        start = col1.button("Start")
        revalidate_links = col2.checkbox("Force revalidate course links")

        if start:
            run_fix()
