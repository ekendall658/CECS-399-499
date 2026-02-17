import os
from datetime import datetime, date, time as dtime

import pytz
import requests
import pandas as pd

from prefect import flow, task, get_run_logger
from prefect.server.schemas.schedules import RRuleSchedule  # Prefect 3 schedule object

TZ = pytz.timezone("America/New_York")

EIA_URL = (
    "https://api.eia.gov/v2/electricity/rto/region-data/data/"
    "?frequency=hourly&data[0]=value&start=2026-02-12T00&end=2026-02-13T00"
    "&sort[0][column]=period&sort[0][direction]=desc&offset=0&length=5000"
)

OUT_CSV = "prefect_sample_eia.csv"


@task(retries=3, retry_delay_seconds=10)
def fetch_eia() -> pd.DataFrame:
    api_key = os.getenv("EK_EIA_API")
    if not api_key:
        raise RuntimeError("EK_EIA_API env var not set")

    r = requests.get(EIA_URL, params={"api_key": api_key}, timeout=60)
    r.raise_for_status()
    payload = r.json()

    records = payload.get("response", {}).get("data", [])
    return pd.DataFrame(records)


@task
def append_to_csv(df: pd.DataFrame) -> str:
    logger = get_run_logger()

    if df is None or df.empty:
        logger.warning("No rows returned; not writing CSV.")
        return OUT_CSV

    df = df.copy()
    df["prefect_run_time_ny"] = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

    file_exists = os.path.exists(OUT_CSV)
    df.to_csv(OUT_CSV, mode="a", header=not file_exists, index=False)

    logger.info("Appended %s rows to %s", len(df), OUT_CSV)
    return OUT_CSV


@flow(name="prefect_sample_eia_flow_to_csv")
def prefect_sample_eia_flow_to_csv() -> str:
    logger = get_run_logger()
    logger.info("Requesting: %s", EIA_URL)

    df = fetch_eia()
    return append_to_csv(df)


def today_at(hour: int, minute: int = 0) -> datetime:
    """
    Returns timezone-aware datetime for today at hour:minute in America/New_York.
    """
    d = date.today()
    dt = datetime.combine(d, dtime(hour, minute))
    return TZ.localize(dt)


def schedule_one_time_run(deployment_name: str, dtstart: datetime) -> None:
    """
    Prefect 3: RRuleSchedule does NOT accept dtstart as a field.
    Put DTSTART inside the rrule string, then RRULE with COUNT=1.
    """
    # Local time in NY, no trailing "Z" because we supply timezone separately
    dtstart_str = dtstart.strftime("%Y%m%dT%H%M%S")

    rrule_text = (
        f"DTSTART:{dtstart_str}\n"
        "RRULE:FREQ=MINUTELY;INTERVAL=1;COUNT=1"
    )

    schedule = RRuleSchedule(
        rrule=rrule_text,
        timezone="America/New_York",
    )

    work_pool = os.getenv("PREFECT_WORK_POOL", "default")

    prefect_sample_eia_flow_to_csv.deploy(
        name=deployment_name,
        work_pool_name=work_pool,
        schedules=[schedule],
        tags=["sample", "eia", "csv", "one-time"],
        build=False,
        push=False,
    )

    print(f"Scheduled deployment '{deployment_name}' at {dtstart.isoformat()} in work pool '{work_pool}'")


def create_today_schedules() -> None:
    now = datetime.now(TZ)

    targets = [
        ("today-0900", today_at(9, 0)),
        ("today-1200", today_at(12, 0)),
        ("today-1500", today_at(15, 0)),
    ]

    for name, dtstart in targets:
        if dtstart <= now:
            print("Time already passed:", name, dtstart.isoformat(), "-> running once immediately")
            prefect_sample_eia_flow_to_csv()
        else:
            schedule_one_time_run(name, dtstart)


if __name__ == "__main__":
    # Creates one-time runs for future target times; runs immediately if already passed.
    create_today_schedules()
