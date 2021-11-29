from django.core.management import call_command
from django.core.management.base import BaseCommand
from percy import percy_snapshot
from selenium import webdriver
from selenium.common.exceptions import ElementNotInteractableException
from selenium.webdriver.common.keys import Keys


class Command(BaseCommand):
    """Execute visual regression tests against a running django server."""

    help = __doc__

    def get_browser(self):
        """Initialize a browser driver to use for taking snapshots."""
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--headless")
        return webdriver.Chrome(options=options)

    def take_snapshots(self, browser):
        """Take DOM snapshots of a set of URLs and upload to Percy."""

        # homepage TODO
        # browser.get("http://localhost:8000/")
        # percy_snapshot(browser, "Home")

        # content page TODO
        # browser.get("http://localhost:8000/content")
        # percy_snapshot(browser, "Content Page")

        # document search with document type filter expanded
        # NOTE: revise to capture search filter panel when we implement it
        browser.get("http://localhost:8000/documents/")
        # open document type filter
        browser.find_element_by_css_selector(".doctype-filter summary").click()
        # click the first option
        browser.find_element_by_css_selector(
            ".doctype-filter li:nth-child(1) label"
        ).click()
        percy_snapshot(browser, "Document Search filter")

        # document search
        browser.get("http://localhost:8000/documents/?q=the+writer&per_page=2")
        percy_snapshot(browser, "Document Search")

        # document detail
        browser.get("http://localhost:8000/documents/2532/")
        percy_snapshot(browser, "Document Details")

        # document scholarship
        browser.get("http://localhost:8000/documents/2532/scholarship/")
        percy_snapshot(browser, "Document Scholarship Records")

        # # mobile menu
        browser.get("http://localhost:8000/documents/#menu")
        percy_snapshot(browser, "Mobile menu")

        # about submenu open on both desktop and mobile
        browser.get("http://localhost:8000/documents/#about-menu")
        # open about menu on desktop
        try:
            browser.find_element_by_id("open-about-menu").click()
        except ElementNotInteractableException:  # ignore on mobile
            pass
        # scroll to top
        browser.find_element_by_tag_name("body").send_keys(Keys.CONTROL + Keys.HOME)
        percy_snapshot(browser, "About submenu")

        # 404 page TODO
        # browser.get("http://localhost:8000/bad-url")
        # percy_snapshot(browser, "404 Page")

        # 500 page TODO
        # browser.get("http://localhost:8000/500")
        # percy_snapshot(browser, "500 Page")

    def handle(self, *args, **options):
        # spin up browser and take snapshots; shut down when finished
        browser = self.get_browser()
        self.take_snapshots(browser)
        browser.quit()
