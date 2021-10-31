# Canvas XID Link Fixer

[Go here for the web UI](https://canvas-xid.herokuapp.com). It may take a moment to spin up the system if it hasn't been used in a while.

An automated utility for fixing broken Canvas image links prefixed with "xid" from Blackboard course imports. Developed for Boise State University.

If you are from Boise State, you will find additional information in [this Google Doc](https://docs.google.com/document/d/1xQ3Ykuhz6SRn2EJ4Oxc5uE-tUCW3pGLF9gBGpLeTzQg/edit?usp=sharing).

## Usage

This program requires either [geckodriver](https://github.com/mozilla/geckodriver/releases) (for Firefox) or [ChromeDriver](https://chromedriver.chromium.org/downloads). 

Install the required libraries with `pip3 install -r requirements.txt`.

Run `python3 main.py -h` for a usage statement. 

## Notes

If you are not from Boise State and want to use this code, please note that I do not provide support for this script, but I won't stop you from using it.
Keep in mind it was written fairly quickly to solve a simple problem, so you may run into issues. **You will need to change the `BASE_URL` constant near the top of the file.**

## Future Improvements
 - Clean up and improve error handling
 - Update to Selenium 4 release when available
 - Improve time efficiency by using BeautifulSoup to get the invalid links (likely not much time improvement, but it could help)
