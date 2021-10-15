import contextlib
import time

from selenium import webdriver
import streamlit as st

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
        st.sidebar.header("Courses")
        for c in st.session_state.courses:
            st.sidebar.markdown(c)

        if st.sidebar.button("Clear"):
            del st.session_state.courses
            st.experimental_rerun()


if __name__ == "__main__":

    alert = st.empty()

    if "username" not in st.session_state or "password" not in st.session_state:
        # Show login screen
        with st.form(key="login_form"):
            st.title("Sign in to Your Boise State Account")
            st.caption("This form saves your Boise State login information locally, "
                       "then submits it whenever a login is prompted.")
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
        st.markdown("Take a second to verify that your course IDs are correct. "
                    "Then, when you're ready, press the **Start** button below. "
                    "Alternatively, you can clear the course list in the sidebar and try again.")

        if st.button("Start"):
            browser = webdriver.Chrome()
            content_container = st.empty()
            status_container = content_container.container()
            progress = status_container.empty()
            status = status_container.empty()
            with contextlib.closing(browser) as driver:
                xid_fix = XIDFixer(driver)
                for i, course in enumerate(st.session_state.courses):
                    progress.progress(int(i * (100 / len(st.session_state.courses))))
                    status.caption("Working on {}...".format(course))
                    time.sleep(2)
                    # xid_fix.do_course(course, st.session_state.username, st.session_state.password)
            progress.progress(100)
            time.sleep(1)
            alert.success("Fix complete for all courses!")
