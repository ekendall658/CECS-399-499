import os
from datetime import datetime, date, time
import pytz
import requests
import pandas as pd

from prefect import flow, task, get_run_logger
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import RRuleSchedule

TZ = pytz.timezone("America/New_York")

EIA_URL = (
    "https://api.eia.gov/v2/electricity/rto/region-data/data/"
    "?frequency=hourly&data[0]=value&start=2026-02-12T00&end=2026-02-13T00"
    "&sort[0][column]=period&sort[0][direction]=desc&offset=0&length=5000"
)

OUT_CSV = "prefect_sample_eia.csv"


@task(retries=3, retry_delay_seconds=10)
def fetch_eia():
    api_key = os.getenv("EK_EIA_API")
    if not api_key:
        raise RuntimeError(" Ella API key not working :( )")

    r = requests.get(EIA_URL, params={"api_key": api_key}, timeout=60)
    r.raise_for_status()
    payload = r.json()

    records = payload.get("response", {}).get("data", [])
    return pd.DataFrame(records)


@task
def append_to_csv(df):
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
def prefect_sample_eia_flow_to_csv():
    logger = get_run_logger()
    logger.info("Requesting: %s", EIA_URL)

    df = fetch_eia()
    return append_to_csv(df)


def today_at(hour, minute=0):
    d = date.today()
    dt = datetime.combine(d, time(hour, minute))
    return TZ.localize(dt)


def schedule_one_time_run(deployment_name, dtstart):
    # One-time schedule using COUNT=1 (runs once at dtstart)
    schedule = RRuleSchedule(
        rrule="FREQ=MINUTELY;INTERVAL=1;COUNT=1",
        timezone="America/New_York",
        dtstart=dtstart,
    )

    dep = Deployment.build_from_flow(
        flow=prefect_sample_eia_flow_to_csv,
        name=deployment_name,
        schedule=schedule,
        work_queue_name="default",
        tags=["sample", "eia", "csv", "one-time"],
    )

    dep.apply()
    print("Scheduled:", deployment_name, "at", dtstart.isoformat())


def create_today_schedules():
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
    # creates runs for the times that have not happened yet, instant go if they already happend
    create_today_schedules()
