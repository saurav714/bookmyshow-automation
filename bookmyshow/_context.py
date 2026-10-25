
from asyncio import AbstractEventLoop
from asyncio import Task
from asyncio import create_task
from asyncio import get_event_loop
from asyncio import sleep
from datetime import datetime
from enum import Enum
from json import JSONDecodeError
from json import loads
from typing import Any
from typing import Callable
from typing import List
from typing import Literal
from typing import Optional
from typing import Tuple
from typing import Type
from typing import Union
from uuid import uuid4

from loguru import logger as CoreLogger
from loguru._logger import Logger
from playwright.async_api import Browser
from playwright.async_api import BrowserContext
from playwright.async_api import ElementHandle
from playwright.async_api import Frame
from playwright.async_api import Locator
from playwright.async_api import Page
from playwright.async_api import Playwright
from playwright.async_api import Request
from playwright.async_api import Response
from playwright.async_api import Route
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from pydantic import BaseModel
from pydantic import field_validator

from ._logging import get_logger


class ProductDetails(BaseModel):
    banner_image_url: Optional[str]
    card_image_url: Optional[str]
    cities: Optional[List[str]]
    code: Optional[str]
    start_date: Optional[datetime]
    start_price: Optional[int]
    max_ticket: Optional[int]
    min_ticket: Optional[int]
    stop_sales: Optional[bool]
    venue: Optional[str]


class SessionDetails(BaseModel):
    @field_validator("availibility")
    @classmethod
    def availibility_(cls, value: str) -> str:
        return value.upper()

    availibility: Optional[str] # "AVAILABLE" | "SELLING_FAST" | "SOLD_OUT"
    city: Optional[str]
    code: Optional[str]
    end_date_time: Optional[datetime]
    product: Optional[str]
    start_date_time: Optional[datetime]
    state: Optional[str]
    total_capacity: Optional[int]
    total_hold: Optional[int]
    total_reserved: Optional[int]
    total_sold: Optional[int]
    venue: Optional[str]


class QueueIt(BaseModel):
    forecast_status: Optional[str]
    expected_service_time: str
    expected_service_time_utc: Optional[datetime]
    users_in_line_ahead_of_you: Optional[int]
    users_in_queue: Optional[int]
    queue_paused: Optional[bool]


class BookMyShow:
    """An instance created to book tickets for a particular event.

    Args:
        endpoint (str): The browser endpoint to use. Must be chromium.

        code (str): The event code.
        quantity (int): Quantity of tickets to book per transaction.

        datetimes (List[datetime]): List of datetime of the event to book. Only one datetime will be selected based on the ascending order of the list, if the selected datetime is not available, the next datetime will be selected.

        categories (List[str]): List of categories to book. Only one category will be selected based on the ascending order of the list, if the selected category is not available, the next category will be selected.

        full_name (str): Full name of the person booking the tickets.
        email (str): Email of the person booking the tickets.
        phone (str): Phone number of the person booking the tickets. Should not be included with the country code.

        payment_method (Optional[Literal[&quot;VISA&quot;, &quot;MASTERCARD&quot;]], optional): Payment method to use. Defaults to None.

        cardholder_name (Optional[str], optional): Cardholder name. Defaults to None.
        card_number (Optional[str], optional: Card number. Defaults to None.
        card_expiry (Optional[datetime], optional: Card expiry date. Defaults to None.
        card_cvv (Optional[str], optional): Card CVV. Defaults to None.
    """
    class Domain(Enum):
        BIGTIX = r"https://mmic.bigtix.io"
        BMS = r"https://my.bookmyshow.com"

        def __str__(self) -> str:
            return self._value_

        def __eq__(self, other: Any) -> bool:
            assert isinstance(other, str)
            return other.lower() == self.value

        def is_startswith(self, other: Any) -> bool:
            assert isinstance(other, str)
            return other.lower.startswith(self.value)


    class AtPage(Enum):
        HOME_PAGE = r"/"

        PRODUCT_INVALID_PAGE = r"/events/<code>"
        PRODUCT_BOOKABLE_PAGE = r"/events/<code>"
        PRODUCT_UNBOOKABLE_PAGE = r"/events/<code>"

        QUEUEIT_PAGE = r"/"

        BOOKING_PAGE = r"/booking/<code>"
        BOOKING_INVALID_PAGE = r"/booking/<code>/invalid"
        BOOKING_SESSIONS_PAGE = r"/booking/<code>/sessions"
        BOOKING_SESSIONS_NO_AVAILABLE_PAGE = r"/booking/<code>/sessions"
        BOOKING_SESSIONS_TICKETS_UNAVAILABLE_PAGE = r"/booking/<code>/sessions"

        BOOKING_QUANTITY_PAGE = r"/booking/<code>/quantity"
        BOOKING_SEATS_PAGE = r"/booking/<code>/seats"

        CHECKOUT_PAGE = r"/checkout"
        CHECKOUT_PATRON_PAGE = r"/checkout/patron"
        CHECKOUT_PAYMENT_PAGE = r"/checkout/payment"

        UNKNOWN_PAGE = r"?"


    QUEUEIT_DOMAIN = r"https://bookmyshowsg.queue-it.net"
    QUEUEIT_URL = f"{QUEUEIT_DOMAIN}/spa-api/queue/bookmyshowsg"

    PRODUCT_API = r"api/v2/live/products"
    STATUS_API = r"api/v2/live/checkBookNowStatus"
    SESSION_API = r"api/v2/live/sessions"


    def __init__(
        self,
        *,
        endpoint: Optional[str] = None,

        code: str,
        quantity: Optional[int] = None,

        datetimes: Optional[List[datetime]] = None,
        categories: Optional[List[str]] = None,

        full_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,

        payment_method: Optional[Literal["VISA", "MASTERCARD"]] = None,
        cardholder_name: Optional[str] = None,
        card_number: Optional[str] = None,
        card_expiry: Optional[datetime] = None,
        card_cvv: Optional[str] = None,
    ):
        self._logger = get_logger(f"{str(uuid4()).upper()[:8]}:{code}")
        self._loop: AbstractEventLoop = get_event_loop()

        self._endpoint: str = endpoint or "http://127.0.0.1:9222"
        self._playwright: Playwright

        self._browser: Browser
        self._headless_browser: Browser

        self._timeout: int = 300000

        self._code: str = code.upper()
        self._quantity: int = int(quantity or 1)
        self._datetimes: List[datetime] = datetimes or [None]
        self._categories: List[str] = categories or [None]
        self._full_name: str = full_name or ""
        self._email: str = email or ""
        self._phone: str = phone or ""
        self._payment_method: Optional[Literal["VISA", "MASTERCARD"]] = payment_method or ""
        self._cardholder_name: Optional[str] = cardholder_name or ""
        self._card_number: Optional[str] = card_number or ""
        self._card_expiry: Optional[datetime] = card_expiry or ""
        self._card_cvv: Optional[str] = card_cvv or ""

        self._product_domain: Optional[Domain] = None
        self._product_details: ProductDetails

        self._debug = __import__(".", fromlist="__debugmode__", level=0)


    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect_over_cdp(self._endpoint, timeout=self._timeout)
        self._headless_browser = await self._playwright.chromium.launch(headless=not self._debug, timeout=self._timeout)

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._browser.close()
        await self._headless_browser.close()
        await self._playwright.stop()

    async def start(self):
        await self.__aenter__()

    async def stop(self):
        await self.__aexit__(None, None, None)

    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return f"<BookMyShow " + \
            f"code={self._code!r}, " + \
            f"quantity={self._quantity!r}, " + \
            f"datetimes={self._datetimes!r}, " + \
            f"categories={self._categories!r}, " + \
            f"full_name={self._full_name!r}, " + \
            f"email={self._email!r}, " + \
            f"phone={self._phone!r}, " + \
            f"payment_method={self._payment_method!r}, " + \
            f"cardholder_name={self._cardholder_name!r}, " + \
            f"card_number={'X' * (len(self._card_number) - 4) + self._card_number[-4:]!r}" if self._card_number else \
            f"card_number={self._card_number!r}"

    @property
    def code(self) -> str:
        return self._code

    @property
    def product_details(self) -> Optional[ProductDetails]:
        return self._product_details

    @classmethod
    def _product_api(
        cls,
        *,
        domain: Domain=Domain.BIGTIX,
        code: Optional[str]=None,
        states: Optional[str]=None
    ) -> str:
        if code:
            return rf"{cls.BIGTIX_DOMAIN if domain == cls.Domain.BIGTIX else cls.BMS_DOMAIN}/" + \
                rf"{cls.PRODUCT_API}/{code.upper()}"

        if states:
            return rf"{cls.BIGTIX_DOMAIN if domain == cls.Domain.BIGTIX else cls.BMS_DOMAIN}/" + \
                rf"{cls.PRODUCT_API}?states={states.replace(' ', '%20')}"

        return rf"{cls.BIGTIX_DOMAIN if domain == cls.Domain.BIGTIX else cls.BMS_DOMAIN}/" + cls.PRODUCT_API

    @classmethod
    def _status_api(
        cls,
        code: str,
        *,
        domain: Domain=Domain.BIGTIX,
    ) -> str:
        return rf"{cls.BIGTIX_DOMAIN if domain == cls.Domain.BIGTIX else cls.BMS_DOMAIN}/" + \
            rf"{cls.STATUS_API}?productCode={code.upper()}"

    @classmethod
    def _booking_url(
        cls,
        code: str,
        *,
        domain: Domain=Domain.BIGTIX,
    ) -> str:
        return rf"{cls.BIGTIX_DOMAIN if domain == cls.Domain.BIGTIX else cls.BMS_DOMAIN}/" + \
            rf"booking/{code.upper()}"

    @classmethod
    def _event_url(
        cls,
        code: str,
        *,
        domain: Domain=Domain.BIGTIX,
    ) -> str:
        return rf"{cls.BIGTIX_DOMAIN if domain == cls.Domain.BIGTIX else cls.BMS_DOMAIN}/" + \
            rf"event/{code.upper()}"


    async def _call(
        self,
        url: str,
        *,
        page: Optional[Page]=None,
        route_predicate: Callable[[str], bool]=lambda _: True,
        route_consumer: Optional[Callable[[Route, Request], None]]=None,
    ) -> Optional[Response]:
        if "_callpage" not in self.__dict__ and page is None:
            self._callpage = await self._headless_browser.new_page()

        page = page or self._callpage

        if route_consumer:
            await page.route(route_predicate, route_consumer)

        response: Response = await page.goto(
            url, wait_until="load", timeout=self._timeout
        )
        if route_consumer:
            await page.unroute(route_predicate, route_consumer)

        if response.status == 403:
            self._logger.debug(f"403 Forbidden, your IP address may be blocked, or you may have been rate limited. <{url}>")
            return response
        elif response.status == 404:
            self._logger.debug(f"404 Not Found, the requested URL was not found. <{url}>")
            return response
        elif response.status == 500:
            self._logger.debug(f"500 Internal Server Error, the server encountered an unexpected condition. <{url}>")
            return response

        if not response.ok:
            self._logger.debug(f"An unexpected error occurred, {response.status} Error, {await response.json()['error']['message']}. <{url}>")
            return response

        return response


    def _request_model(self, request: Union[Request, str]) -> Optional[Type[BaseModel]]:
        url = request.url if isinstance(request, Request) else request

        if url.startswith(self.QUEUEIT_URL):
            return QueueIt
        if url.find(f"{self.SESSION_API}?city="):
            return SessionDetails

        return None


    async def _interpret_data(self, request: Request, datatype: Type[BaseModel]) -> Optional[BaseModel]:
        response: Response = await request.response()
        data: dict = await response.json()

        if datatype is SessionDetails:
            return [
                datatype(
                    availibility = s["avail"],
                    city = s["city"],
                    code = s["code"],
                    end_date_time = datetime.strptime(s["endDateTime"], "%Y-%m-%dT%H:%M:%S.%fZ") if s["endDateTime"] else None,
                    product = s["product"],
                    start_date_time = datetime.strptime(s["startDateTime"], "%Y-%m-%d %H:%M:%S"),
                    state = s["state"],
                    total_capacity = s["totalCapacity"],
                    total_hold = s["totalHold"],
                    total_reserved = s["totalReserved"],
                    total_sold = s["totalSold"],
                    venue = s["venue"]
                )
                for s in data["data"]
            ]

        if datatype is QueueIt:
            if not data.get("ticket"):
                return None

            time_string = data["ticket"]["expectedServiceTimeUTC"][:-2] + "Z"
            return datatype(
                forecast_status=data["forecastStatus"],
                expected_service_time=data["ticket"]["expectedServiceTime"],
                expected_service_time_utc=datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%S.%fZ"),
                users_in_line_ahead_of_you=data["ticket"]["usersInLineAheadOfYou"],
                users_in_queue=data["ticket"]["usersInQueue"],
                queue_paused=data["ticket"]["queuePaused"]
            )

        self._logger.debug(f"Unknown datatype <{datatype}>")
        return None


    async def _current_state(self, page: Page) -> AtPage:
        # /
        homepage: Locator = page.locator("div[class^='bmsportal-homepage-productlisttitle']")

        # /events/..
        product: Locator = page.locator("div[class^='bmsportal-product-details-main-title']")
        product_invalid: Locator = page.locator("div[class^='bigtix-portal-error-page__title']", has_text="Uh oh!")
        product_bookable: Locator = page.locator("button[class^='BookButton__StyledButton']")

        # /booking/..
        booking: Locator = page.locator("div[class^='ClickToAccept__StyledButtonContainer']")

        # /booking/../invalid
        booking_invalid: Locator = page.locator("div[class^='bigtix-portal-error-page__title']", has_text="Uh oh!")

        # /booking/../sessions
        booking_sessions: Locator = page.locator("div[class^='bigtix-sessions-list-v2__sessions']")
        booking_no_available_sessions: Locator = page.locator("div[class^='bigtix-booking-message-header']", has_text="No available sessions!")
        booking_tickets_unavailable: Locator = page.locator("div[class^='bigtix-booking-message-header']", has_text="Tickets unavailable")

        # /booking/../quantity
        booking_quantity: Locator = page.locator("div[class='bigtix-quantity-stepper__quantity']")

        # /booking/../seats
        booking_seats: Locator = page.locator("div[class^='bigtix-svg-map']")

        # checkout/
        checkout: Locator = page.locator("div[class^='Remove__StyledRemove']")

        # checkout/patron
        checkout_patron: Locator = page.locator("div[class^='bigtix-formitem__patronInfo-field--fullName']")

        # checkout/payment
        checkout_payment: Locator = page.locator("div[class^='bigtix-card__content']")

        if page.url.endswith("/checkout/payment") and await payment.is_visible():
            return self.AtPage.CHECKOUT_PAYMENT_PAGE

        elif page.url.endswith("/checkout/patron") and await checkout_patron.is_visible():
            return self.AtPage.CHECKOUT_PATRON_PAGE

        elif page.url.endswith("/checkout") and await checkout.is_visible():
            return self.AtPage.CHECKOUT_PAGE

        elif page.url.endswith("/seats") and await booking_seats.is_visible():
            return self.AtPage.BOOKING_SEATS_PAGE

        elif page.url.endswith("/quantity") and await booking_quantity.is_visible():
            return self.AtPage.BOOKING_QUANTITY_PAGE

        elif page.url.endswith("/sessions") and await booking_tickets_unavailable.is_visible():
            return self.AtPage.BOOKING_SESSIONS_TICKETS_UNAVAILABLE_PAGE

        elif page.url.endswith("/sessions") and await booking_no_available_sessions.is_visible():
            return self.AtPage.BOOKING_NO_AVAILABLE_SESSIONS_PAGE

        elif page.url.endswith("/sessions") and await booking_sessions.is_visible():
            return self.AtPage.BOOKING_SESSIONS_PAGE

        elif page.url.endswith("/invalid") and await booking_invalid.is_visible():
            return self.AtPage.BOOKING_INVALID_PAGE

        elif page.url.endswith("/booking") and await booking.is_visible():
            return self.AtPage.BOOKING_PAGE

        elif page.url.find("/events/") and await product_invalid.is_visible():
            return self.AtPage.PRODUCT_INVALID_PAGE

        elif page.url.find("/events/") and await product_bookable.is_visible():
            return self.AtPage.PRODUCT_BOOKABLE_PAGE

        elif page.url.find("/events/") and await product.is_visible():
            return self.AtPage.PRODUCT_UNBOOKABLE_PAGE

        elif await homepage.is_visible():
            return self.AtPage.HOME_PAGE

        elif page.url.startswith(self.QUEUE_URL):
            return self.AtPage.QUEUEIT_PAGE

        return self.AtPage.UNKNOWN_PAGE


    async def _await_page_loaded(self, page: Page) -> None:
        while await self._current_state(page) == self.AtPage.UNKNOWN_PAGE:
            await sleep(0.05)


    async def _goto_product_page(self, page: Page) -> AtPage:
        bms_url: str = self._event_url(self._code, domain=self.Domain.BMS)
        bigtix_url: str = self._event_url(self._code, domain=self.Domain.BIGTIX)

        await self._call(bms_url, page=page)
        await self._await_page_loaded(page)
        at_page: AtPage = await self._current_state(page)

        if (
            at_page != self.AtPage.PRODUCT_INVALID_PAGE
            and at_page in (self.AtPage.PRODUCT_BOOKABLE_PAGE, self.AtPage.PRODUCT_UNBOOKABLE_PAGE)
        ):
            return at_page

        await self._call(bigtix_url, page=page)
        await self._await_page_loaded(page)
        return await self._current_state(page)


    async def _goto_booking_page(self, page: Page) -> AtPage:
        bms_url: str = self._booking_url(self._code, domain=self.Domain.BMS)
        bigtix_url: str = self._booking_url(self._code, domain=self.Domain.BIGTIX)

        await self._call(bms_url, page=page)
        await self._await_page_loaded(page)
        at_page: AtPage = await self._current_state(page)

        if (
            at_page != self.AtPage.BOOKING_INVALID_PAGE
            and at_page in (self.AtPage.BOOKING_PAGE, self.AtPage.QUEUEIT_PAGE)
        ):
            return at_page

        await self._call(bigtix_url, page=page)
        await self._await_page_loaded(page)
        return await self._current_state(page)


    async def _one_click_run(self, page: Page) -> None:

        queue_it: Optional[QueueIt] = None
        sessions: List[SessionDetails] = []

        async def consumer(route: Route, request: Request) -> None:
            nonlocal queue_it, sessions

            route.continue_()
            datatype: Type[BaseModel] = self._request_model(request)

            if not datatype:
                return

            data: BaseModel = await self._interpret_data(request, datatype)
            if not data:
                return

            if isinstance(data, QueueIt):
                queue_it = data
                return

            if isinstance(data, SessionDetails):
                sessions.extend(data)
                return

        async def set_route() -> None:
            await page.route(
                url=lambda u: self._request_model(u),
                handler=consumer
            )

        await set_route()
        page.on("navigate", lambda: self._loop.create_task(set_route()))


        if await self._goto_product_page(page) == self.AtPage.PRODUCT_INVALID_PAGE:
            self._logger.warning(f"Product <{self._code}> is invalid. <{page.url}>")


        if await self._current_state(page) == self.AtPage.PRODUCT_UNBOOKABLE_PAGE:
            self._logger.warning(f"Product <{self._code}> is unbookable. Proceeding to use alternate method. <{page.url}>")

            if await self._goto_booking_page(page) == self.AtPage.BOOKING_INVALID_PAGE:
                self._logger.warning(f"Booking <{self._code}> is invalid. <{page.url}>")
                self._logger.warning(f"The process has been terminated.")
                return


        elif await self._current_state(page) == self.AtPage.PRODUCT_BOOKABLE_PAGE:
            await page.click("button[class^='BookButton__StyledButton']")
            await self._await_page_loaded(page)

            if await self._current_state(page) == self.AtPage.QUEUEIT_PAGE:
                self._logger.info(f"Product <{self._code}> is in queue. <{page.url}>")

                while await self._current_state(page) == self.AtPage.QUEUEIT_PAGE:
                    await sleep(0.05)


        await self._await_page_loaded(page)

        if await self._current_state(page) == self.AtPage.BOOKING_PAGE:
            await page.eval_on_selector(
                "div[class^='.ClickToAccept__StyledContent']",
                "el -> el.scrollTop = el.scrollHeight"
            )
            await page.click("div[class^='ClickToAccept__StyledButtonContainer']")

        await self._await_page_loaded(page)

        if await self._current_state(page) == self.AtPage.BOOKING_SESSIONS_NO_AVAILABLE_PAGE:
            self._logger.warning(f"No available sessions for the product.")
            self._logger.warning(f"The process has been terminated.")
            return


        next_button: Locator = page.locator("#bigtix-booking-next-page")
        session_code: Optional[str] = None
        elements: List[ElementHandle] = []

        for dt in self._datetimes:

            for ss in sessions:
                if ss.start_date_time != dt:
                    continue

                session_code = ss.code
                break

            else:
                self._logger.warning(f"Session at datetime <{dt}> is unavailable.")
                continue

            self._logger.info(f"Booking session <{session_code}> at datetime <{dt}>.")

            await page.click(f"button[data-session='{session_code}']")
            await self._await_page_loaded(page)

            if await self._current_state(page) == self.AtPage.BOOKING_SESSIONS_TICKETS_UNAVAILABLE_PAGE:
                logger.warning(f"Bulk tickets are unavailable for session <{session_code}> at datetime <{dt}>.")
                continue


            if await self._current_state(page) == self.AtPage.BOOKING_QUANTITY_PAGE:
                await page.fill(
                    "input[class^='bigtix-quantity-stepper__quantity']",
                    str(self._quantity)
                )
                await next_button.click()


            await self._await_page_loaded(page)

            assert self._current_state(page) == self.AtPage.BOOKING_SEATS_PAGE

            for cat in self._categories:
                elements = await page.query_selector_all(
                    f"polygon[data-section-name^='{cat}]" + \
                    ":not(.bigtix-overview-map__area-hidden)"
                )

                if not polygons:
                    self._logger.warning(f"Category <{cat}> is unavailable for session <{session_code}> at datetime <{dt}>.")
                    continue

                break

            else:
                self._logger.warning(f"All categories {self._categories} are unavailable for session <{session_code}> at datetime <{dt}>.")
                continue

            break

        else:
            self._logger.warning(f"All datetimes {self._datetimes} are unavailable.")
            self._logger.warning(f"The process has been terminated.")
            return

        assert elements

        for el in elements:
            box = await el.bounding_box()
            await page.mouse.click(
                x=box["x"] + box["width"] / 2,
                y=box["y"] + box["height"] / 2,
                button="left"
            )

            await sleep(0.1)

            if await page.locator("div[class^='bigtix-booking-ordersummary-categories']").is_visible():
                break


        if not await next_button.is_visible():
            self._logger.warning(f"Booking <{session_code}> at datetime <{dt}> has failed.")
            self._logger.warning(f"The process has been terminated.")
            return

        await next_button.click()

        await self._await_page_loaded(page)

        assert self._current_state(page) == self.AtPage.CHECKOUT_PAGE

        await page.click(
            "button[class^='bigtix-checkout_shopping_cart_sticky_checkout_card_next_button']"
        )

        await self._await_page_loaded(page)

        assert self._current_state(page) == self.AtPage.CHECKOUT_PATRON_PAGE

        await page.fill("input[name='fullName']", self._full_name)
        await page.fill("input[name='email']", self._email)
        await page.fill("input[name='phone']", self._phone)
        await page.check(f"div[name^='{self._code}.TERMSCONDITIONS']")


    async def one_click_run(self) -> Page:
        context: BrowserContext = await self._browser.new_context()
        await context.clear_cookies()
        page: Page = await context.new_page()
        self._loop.create_task(self._one_click_run(page))
        return page


class BookMyShowSettings(BaseModel):
    endpoint: Optional[str]

    code: str
    quantity: Optional[int]

    datetimes: Optional[List[datetime]]
    categories: Optional[List[str]]

    full_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]

    payment_method: Optional[Literal["VISA", "MASTERCARD"]]
    cardholder_name: Optional[str]
    card_number: Optional[str]
    card_expiry: Optional[datetime]
    card_cvv: Optional[str]


class BookMyShowAutomation:
    def __init__(self):
        self._logger: Logger = get_logger("context-manager")
        self._loop: AbstractEventLoop = get_event_loop()
        self._instances: List[BookMyShow] = []

        self._state: Literal["running", "stopped"] = "stopped"
        self._process: Task[self._await_input] = None

    async def start(self):
        self._process = self._loop.create_task(self._await_input())
        self._logger.info("Process started.")
        self._state = "running"

        while True:
            await sleep(10)

    async def stop(self):
        self._process.cancel("Process stopped.")

        for ins in self._instances:
            ins.stop()

    def register(self, settings: BookMyShowSettings) -> None:
        bms = BookMyShow(**settings.dict())
        self._logger.info(f"Instance {repr(bms)} has been created.")
        self._loop.create_task(bms.one_click_run())
        self._instances.append(bms)

    @property
    def is_running(self) -> bool:
        return self._state == "running"

    async def _await_input(self) -> None:
        while True:
            strings: str = input()

            try:
                decoded: dict = json.loads(strings)

            except JSONDecodeError:
                continue

            finally:
                self.register(BookMyShowSettings(**decoded))
