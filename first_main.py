import asyncio
import random
import re
import time
import json
import httpx
import os
import sys
from dotenv import load_dotenv
from exc_for_weather_api import FatalError, ApiKeyError, InvalidRequestBodyError
from dataclasses import dataclass
from collections import Counter


load_dotenv()

URL = "https://api.weatherapi.com/v1/current.json"
API_KEY = os.getenv("WEATHER_API_KEY")

MAX_COUNT_ATTMEPTS = 4
BASE_PAUSE = 0.5
CEILING_PAUSE = 6


@dataclass
class InfoWeather:
    city: str
    region: str | None = None
    country: str | None = None
    localtime: str | None = None
    last_updated: str | None = None
    temp_c: float | None = None
    condition: str | None = None
    wind_kph: float | None = None
    will_it_rain: float | None = None
    status_http: int | None = None
    error_code: int | None = None
    error_message: str | None = None


def to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def from_api_dict_to_infoweather(city, data):
    if not isinstance(data, dict):
        raise TypeError(f"data ожидается dict: type(data) = {type(data)}")
    location = data["location"]
    current = data["current"]
    region = location.get("region")
    country = location.get("country")
    localtime = location.get("localtime")
    last_updated = current.get("last_updated")
    temp_c = current["temp_c"]
    condition = current.get("condition", {"text": None}).get("text")
    wind_kph = to_float(current.get("wind_kph"))
    will_it_rain = to_float(current.get("will_it_rain"))
    return InfoWeather(
        city=city,
        region=region,
        country=country,
        localtime=localtime,
        last_updated=last_updated,
        temp_c=temp_c,
        condition=condition,
        wind_kph=wind_kph,
        will_it_rain=will_it_rain,
    )


async def get_weather_one_attempts(url, params, client):
    response = await client.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return data


async def weather_by_city(city: str, client, sem):
    """
    Одна task может отправить несколько попыток для города.
    Пока одна корутина ждет ответ, другая может отправлять свой, если не превышен лимит корутин, которые вошли в защищенный участок.
    """
    params = {"key": API_KEY, "q": city, "lang": "ru"}
    async with sem:
        for attempt in range(1, MAX_COUNT_ATTMEPTS + 1):
            pause_for_repeat = random.uniform(
                0, min(CEILING_PAUSE, BASE_PAUSE * 2 ** (attempt - 1))
            )
            try:
                data = await get_weather_one_attempts(URL, params, client)
                result_attempts = from_api_dict_to_infoweather(city, data)
                return result_attempts
            except (KeyError, AttributeError, TypeError) as e:
                return InfoWeather(
                    city=city, error_message=f"Неожиданный формат ответа: {repr(e)}"
                )

            except httpx.RequestError as e:
                result_attempts = InfoWeather(city=city, error_message=repr(e))
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                try:
                    response_json = e.response.json()
                except json.JSONDecodeError:
                    response_json = {}
                if not isinstance(response_json, dict):
                    response_json = {}

                error = response_json.get("error")
                if not isinstance(error, dict):
                    error = {}

                error_code = error.get("code")
                message = error.get("message") or "Сообщение API утеряно)"
                result_attempts = InfoWeather(
                    city=city,
                    status_http=status_code,
                    error_code=error_code,
                    error_message=message,
                )
                if status_code == 401 or status_code == 403:
                    raise ApiKeyError(message, status_code, error_code) from e
                elif status_code == 400:
                    if error_code == 1006:
                        return result_attempts
                    if error_code != 9999:
                        raise InvalidRequestBodyError(
                            message, status_code, error_code
                        ) from e
                else:
                    if status_code < 500 and status_code != 429:
                        raise FatalError(message, status_code, error_code) from e
            except httpx.InvalidURL as e:
                raise FatalError("Неправильный URL") from e
            if attempt != MAX_COUNT_ATTMEPTS:
                await asyncio.sleep(pause_for_repeat)
        return result_attempts


def input_cities() -> list:
    input_user = input(
        'Введите города через запятую(", " ),\nлибо введите test и будет использован тестовый список городов: '
    )
    if input_user == "test":
        cities = [
            # Россия — 49 городов английскими буквами
            "Moscow",
            "Saint Petersburg",
            "Novosibirsk",
            "Yekaterinburg",
            "Kazan",
            "Nizhny Novgorod",
            "Chelyabinsk",
            "Samara",
            "Omsk",
            "Rostov-on-Don",
            "Ufa",
            "Krasnoyarsk",
            "Voronezh",
            "Perm",
            "Volgograd",
            "Krasnodar",
            "Saratov",
            "Tyumen",
            "Tolyatti",
            "Izhevsk",
            "Barnaul",
            "Ulyanovsk",
            "Irkutsk",
            "Khabarovsk",
            "Yaroslavl",
            "Vladivostok",
            "Makhachkala",
            "Tomsk",
            "Orenburg",
            "Kemerovo",
            "Novokuznetsk",
            "Ryazan",
            "Astrakhan",
            "Naberezhnye Chelny",
            "Penza",
            "Lipetsk",
            "Kirov",
            "Cheboksary",
            "Tula",
            "Kaliningrad",
            "Balashikha",
            "Kursk",
            "Sochi",
            "Stavropol",
            "Ulan-Ude",
            "Tver",
            "Magnitogorsk",
            "Ivanovo",
            "Bryansk",
            # 10 российских городов, повторённых только по-русски
            "Москва",
            "Санкт-Петербург",
            "Новосибирск",
            "Екатеринбург",
            "Казань",
            "Нижний Новгород",
            "Челябинск",
            "Самара",
            "Омск",
            "Ростов-на-Дону",
            # 10 городов мира английскими буквами
            "London",
            "New York",
            "Tokyo",
            "Paris",
            "Berlin",
            "Beijing",
            "Rome",
            "Madrid",
            "Toronto",
            "Sydney",
        ]
    else:
        cities = [c for c in re.split(r",\s*", input_user) if c]
    return cities


def pars_output(obj, first):
    headers = [
        "Город",
        "Регион",
        "Страна",
        "Местное время",
        "Температура",
        "Состояние",
        "Ветер км/ч",
        "Дождь?",
    ]

    w_city = 18
    w_region = 30
    w_country = 24
    w_localtime = 19
    w_temp = 11
    w_condition = 24
    w_wind = 10
    w_rain = 6
    widths = [
        w_city,
        w_region,
        w_country,
        w_localtime,
        w_temp,
        w_condition,
        w_wind,
        w_rain,
    ]
    sep = (sum(widths) + 3 * (len(headers) - 1)) * "—"

    if first:
        print(sep)
        for h, w in zip(headers, widths):
            print(f"{h:^{w}}", end=" | ")
        print()
    print(sep)

    if obj.error_message is None:
        values = [
            obj.city,
            obj.region,
            obj.country,
            obj.localtime,
            obj.temp_c,
            obj.condition,
            obj.wind_kph,
            obj.will_it_rain,
        ]
        for v, w in zip(values, widths):
            print(f"{v:<{w}}", end=" | ")
        print()
    else:
        w_msg = len(sep) - w_city - 3 - w_region - 3 - w_country - 3
        print(
            f"{obj.city:<{w_city}} | "
            f"http код: {obj.status_http:<{w_region - len("http код: ")}} | "
            f"код ошибки: {obj.error_code:<{w_country - len("код ошибки: ")}} | "
            f"{obj.error_message:<{w_msg}} |"
        )
        print()


def print_summary(results: list[InfoWeather]) -> None:
    failed = Counter(r.error_message for r in results if r.error_message is not None)
    success = len(results) - failed.total()

    print(f"\nУспешно:    {success}")
    print(f"Неуспешных: {failed.total()}")
    if not failed:
        return

    indent = " " * len("Неуспешных: ")
    width = len(str(max(failed.values())))
    for reason, count in failed.most_common():
        print(f"{indent}{count:>{width}}    {reason}")


async def main():
    cities = input_cities()
    results = []
    sem = asyncio.Semaphore(8)
    start = time.perf_counter()

    async with httpx.AsyncClient() as client:
        tasks = [
            asyncio.create_task(weather_by_city(city, client, sem)) for city in cities
        ]
        pending = set(tasks)
        first = True
        try:
            while pending:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                for d in done:
                    task_done = d.result()
                    pars_output(task_done, first)
                    results.append(task_done)
                    if first:
                        first = False
        except FatalError as e:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            print(f"Работа остановлена: {e}")
            return
        finally:
            print(f"\nВремя работы: {time.perf_counter() - start}")

    print_summary(results)


if __name__ == "__main__":
    if API_KEY is None:
        print("Отсутствует api ключ")
        sys.exit(1)
    asyncio.run(main())
