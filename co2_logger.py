# CO2 logging to a CSV file: one row per minute, containing the mean and
# standard deviation of the CO2 readings sampled within that minute.
#
# Can be used two ways:
#   1. Standalone:  python3 co2_logger.py [--path ...] [--interval ...] [--window ...]
#   2. Embedded:    feed samples into CO2LogRecorder from your own loop
#                    (the dashboard uses this to offer a manual Start/Stop
#                    logging button).

import argparse
import csv
import statistics
import time
from pathlib import Path

from config import make_co2_sensor


class CO2LogRecorder:
    """Accumulates CO2 samples and writes one mean/std row per window.

    Feed it one sample at a time with add(timestamp, co2). Every time the
    first sample in the window is `window` seconds old it writes a row
    (mean, std dev, n) to the CSV and starts a fresh window. call emit()
    at the end to flush a partially filled window.
    """

    def __init__(self, path="co2_log.csv", window=60.0, extra_fields=(), mode="average"):
        if mode not in ("average", "raw"):
            raise ValueError("mode must be 'average' or 'raw'")
        self.path = Path(path)
        self.window = window
        self.mode = mode
        self.extra_fields = tuple(extra_fields)
        self._buffer = []      # (timestamp, co2_ppm, extra_dict) -- average mode
        self._written = 0      # rows written -- raw mode
        self._first_ts = None  # first sample time -- raw mode
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_header()

    # -------------------------------------------------------------- files

    def _write_header(self):
        if not self.path.exists() or self.path.stat().st_size == 0:
            if self.mode == "average":
                columns = ["timestamp", "co2_mean_ppm", "co2_std_ppm", "n_samples"]
                columns += [f"{field}_mean" for field in self.extra_fields]
            else:  # raw: one row per measurement
                columns = ["timestamp", "co2_ppm"] + list(self.extra_fields)
            with open(self.path, "a", newline="") as handle:
                csv.writer(handle).writerow(columns)

    @staticmethod
    def _fmt(value):
        if value is None:
            return ""
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return str(value)

    def _write_row_average(self, timestamp, mean, stdev, count):
        columns = [
            timestamp,
            f"{mean:.2f}",
            "" if stdev is None else f"{stdev:.2f}",
            count,
        ]
        for field in self.extra_fields:
            values = [
                sample.get(field)
                for _, _, sample in self._buffer
                if sample.get(field) is not None
            ]
            columns.append(f"{statistics.fmean(values):.2f}" if values else "")
        with open(self.path, "a", newline="") as handle:
            csv.writer(handle).writerow(columns)

    def _write_row_raw(self, timestamp, co2, extra):
        columns = [
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)),
            f"{co2:.2f}",
        ]
        columns += [self._fmt(extra.get(field)) for field in self.extra_fields]
        with open(self.path, "a", newline="") as handle:
            csv.writer(handle).writerow(columns)

    # ------------------------------------------------------------- state

    @property
    def count(self):
        """Samples in the current window, or rows written (raw mode)."""
        return self._written if self.mode == "raw" else len(self._buffer)

    @property
    def since(self):
        """Timestamp of the first sample/row of the current logging run."""
        if self.mode == "raw":
            return self._first_ts
        return self._buffer[0][0] if self._buffer else None

    # ------------------------------------------------------------ logging

    def add(self, timestamp, co2, extra=None):
        """Add one sample; average mode emits when the window fills."""
        extra = extra or {}
        if self.mode == "raw":
            if self._first_ts is None:
                self._first_ts = timestamp
            self._written += 1
            self._write_row_raw(timestamp, co2, extra)
            return
        self._buffer.append((timestamp, co2, extra))
        if self._buffer and self._buffer[-1][0] - self._buffer[0][0] >= self.window:
            self.emit()

    def emit(self):
        """Write the mean/std of the current window and reset it (average)."""
        if self.mode != "average" or not self._buffer:
            return
        values = [value for _, value, _ in self._buffer]
        mean = statistics.fmean(values)
        stdev = statistics.stdev(values) if len(values) >= 2 else None
        timestamp = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(self._buffer[-1][0])
        )
        self._write_row_average(timestamp, mean, stdev, len(values))
        self._buffer.clear()


class CO2Logger:
    """Standalone continuous logger: samples and writes per-minute rows."""

    def __init__(self, path="co2_log.csv", sample_interval=2.0, window=60.0,
                 average=0.0, mode="average", sensor=None):
        self.path = Path(path)
        self.sample_interval = sample_interval
        self.window = window
        self.average = average
        self.mode = mode
        self.sensor = sensor if sensor is not None else make_co2_sensor()

    def run(self):
        if self.average is not None:
            self.sensor.set_average(float(self.average))
        recorder = CO2LogRecorder(self.path, self.window, mode=self.mode)
        try:
            while True:
                now = time.time()
                try:
                    co2 = self.sensor.get_co2()
                    recorder.add(now, co2)
                    print(
                        f"\r{co2:7.1f} ppm  (samples this window: {recorder.count})",
                        end="",
                        flush=True,
                    )
                except Exception as exc:
                    print(f"\r! read failed: {exc}", flush=True)
                time.sleep(self.sample_interval)
        except KeyboardInterrupt:
            print()
            if recorder.count:  # flush the unfinished window so nothing is lost
                recorder.emit()
            print(f"Log written to {recorder.path}")
        finally:
            self.sensor.close()


def main():
    parser = argparse.ArgumentParser(description="Log per-minute CO2 mean/std to CSV.")
    parser.add_argument("--path", default="co2_log.csv", help="output CSV file")
    parser.add_argument("--interval", type=float, default=2.0, help="sample interval (s)")
    parser.add_argument("--window", type=float, default=60.0, help="summary window (s)")
    parser.add_argument("--average", type=float, default=0.0,
                        help="sensor averaging filter in s (0 = off, hand averaging)")
    parser.add_argument("--mode", choices=["average", "raw"], default="average",
                        help="average = per-minute mean/std, raw = one row per measurement")
    args = parser.parse_args()

    CO2Logger(
        path=args.path,
        sample_interval=args.interval,
        window=args.window,
        average=args.average,
        mode=args.mode,
    ).run()


if __name__ == "__main__":
    main()