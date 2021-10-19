import contextlib
import time
import datetime

from selenium import webdriver
import streamlit as st
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.utils import ChromeType

from fixer import XIDFixer

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


def run_fix():
    start_time = time.time()
    browser = webdriver.Chrome(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    progress_container = btn_container.container()
    progress = progress_container.empty()
    status = progress_container.empty()

    total_failed = 0
    total_attempted = 0

    with contextlib.closing(browser) as driver:
        xid_fix = XIDFixer(driver)
        for i, course in enumerate(st.session_state.courses):
            progress.progress(int(i * (100 / len(st.session_state.courses))))
            status.caption("Working on {}...".format(course))
            failed_items, attempted_items, err = xid_fix.do_course(course, st.session_state.username,
                                                              st.session_state.password, revalidate_links)

            if err:
                if err == "login_fail":
                    alert.error("Failed to log into your Boise State account. Please log out "
                                "and re-enter your information.")
                else:
                    alert.error("An unknown error occurred. Code: {}. Stopping.".format(err))
                break
            else:
                total_failed += failed_items
                total_attempted += attempted_items
    if not err:
        progress.progress(100)
        status.caption("Done!")
        alert.success("Fix complete for all courses! {} of {} attempted items were successful ({}%). Time: {}.".format(
            total_attempted - total_failed, total_attempted,
            int((total_attempted - total_failed) / total_attempted),
            datetime.timedelta(seconds=time.time() - start_time)
        ))

    time.sleep(3)
    if btn_container.button("Rerun"):
        run_fix()


if __name__ == "__main__":

    alert = st.empty()

    # TODO: Add state for when the program is waiting for the user to confirm 2FA

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
            submitted = st.form_submit_button("Start Fixing")

            if submitted:
                st.session_state.courses = courses.split()
                st.experimental_rerun()
    else:
        draw_sidebar()

        st.title("Course Fix")
        st.markdown("Take a second to verify that your course links/IDs are correct. "
                    "Then, when you're ready, press the **Start** button below. "
                    "Alternatively, you can clear the course list in the sidebar and try again.")

        st.markdown("**Note: You will likely be asked to complete Duo authentication on your device.**")

        btn_container = st.empty()
        col1, col2 = btn_container.columns(2)
        start = col1.button("Start")
        revalidate_links = col2.checkbox("Force revalidate course links")

        if start:
            run_fix()
