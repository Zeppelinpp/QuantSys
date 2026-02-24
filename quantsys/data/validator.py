"""Data quality validator."""

from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd
from loguru import logger


@dataclass
class ValidationError:
    """Validation error record."""

    row_index: int
    column: str
    error_type: str
    message: str
    value: Any


class DataValidator:
    """Validate market data quality."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.errors: List[ValidationError] = []

    def validate_ohlc(self, df: pd.DataFrame) -> List[ValidationError]:
        """Validate OHLC logic.

        Rules:
        - low <= open <= high
        - low <= close <= high
        - low <= high
        """
        errors = []

        required_cols = ["open", "high", "low", "close"]
        for col in required_cols:
            if col not in df.columns:
                logger.warning(f"Missing column {col}, skipping OHLC validation")
                return errors

        for idx, row in df.iterrows():
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]

            # Check low <= high
            if l > h:
                errors.append(
                    ValidationError(
                        row_index=idx,
                        column="low/high",
                        error_type="ohlc_logic",
                        message=f"low ({l}) > high ({h})",
                        value=(l, h),
                    )
                )

            # Check open within range
            if o < l or o > h:
                errors.append(
                    ValidationError(
                        row_index=idx,
                        column="open",
                        error_type="ohlc_logic",
                        message=f"open ({o}) outside [low ({l}), high ({h})]",
                        value=o,
                    )
                )

            # Check close within range
            if c < l or c > h:
                errors.append(
                    ValidationError(
                        row_index=idx,
                        column="close",
                        error_type="ohlc_logic",
                        message=f"close ({c}) outside [low ({l}), high ({h})]",
                        value=c,
                    )
                )

        return errors

    def validate_price_range(
        self,
        df: pd.DataFrame,
        min_price: float = 0.01,
        max_price: float = 10000.0,
    ) -> List[ValidationError]:
        """Validate price is within reasonable range."""
        errors = []
        price_cols = ["open", "high", "low", "close"]

        for col in price_cols:
            if col not in df.columns:
                continue

            for idx, row in df.iterrows():
                price = row[col]

                if price <= 0:
                    errors.append(
                        ValidationError(
                            row_index=idx,
                            column=col,
                            error_type="price_range",
                            message=f"Price must be positive, got {price}",
                            value=price,
                        )
                    )
                elif price < min_price:
                    errors.append(
                        ValidationError(
                            row_index=idx,
                            column=col,
                            error_type="price_range",
                            message=f"Price below minimum {min_price}, got {price}",
                            value=price,
                        )
                    )
                elif price > max_price:
                    errors.append(
                        ValidationError(
                            row_index=idx,
                            column=col,
                            error_type="price_range",
                            message=f"Price above maximum {max_price}, got {price}",
                            value=price,
                        )
                    )

        return errors

    def validate_volume(self, df: pd.DataFrame) -> List[ValidationError]:
        """Validate volume is non-negative."""
        errors = []

        if "volume" not in df.columns:
            return errors

        for idx, row in df.iterrows():
            vol = row["volume"]
            if vol < 0:
                errors.append(
                    ValidationError(
                        row_index=idx,
                        column="volume",
                        error_type="volume_negative",
                        message=f"Volume cannot be negative, got {vol}",
                        value=vol,
                    )
                )

        return errors

    def validate_timestamp_continuity(
        self,
        df: pd.DataFrame,
        expected_freq: str = "1min",
    ) -> List[ValidationError]:
        """Validate timestamp continuity.

        Checks for gaps in the time series.
        """
        errors = []

        if "timestamp" not in df.columns:
            return errors

        if len(df) < 2:
            return errors

        df_sorted = df.sort_values("timestamp")
        timestamps = pd.to_datetime(df_sorted["timestamp"])

        # Calculate expected intervals
        expected_interval = pd.Timedelta(expected_freq)

        for i in range(1, len(timestamps)):
            actual_interval = timestamps.iloc[i] - timestamps.iloc[i - 1]

            # Allow for some tolerance (e.g., market gaps are expected)
            # Only flag gaps that are not market close periods
            if actual_interval > expected_interval * 2:
                # Check if it's a market open/close gap (normal)
                t1 = timestamps.iloc[i - 1]
                t2 = timestamps.iloc[i]

                # Skip if it's overnight or weekend gap
                if t1.date() != t2.date():
                    continue

                errors.append(
                    ValidationError(
                        row_index=df_sorted.index[i],
                        column="timestamp",
                        error_type="timestamp_gap",
                        message=f"Unexpected gap: {actual_interval} between {t1} and {t2}",
                        value=(t1, t2),
                    )
                )

        return errors

    def validate(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Run all validations and return report."""
        all_errors = []

        all_errors.extend(self.validate_ohlc(df))
        all_errors.extend(self.validate_price_range(df))
        all_errors.extend(self.validate_volume(df))
        all_errors.extend(self.validate_timestamp_continuity(df))

        self.errors = all_errors

        return {
            "total_rows": len(df),
            "error_count": len(all_errors),
            "error_types": list(set(e.error_type for e in all_errors)),
            "errors": all_errors,
            "is_valid": len(all_errors) == 0,
        }

    def log_errors(self, max_errors: int = 10) -> None:
        """Log validation errors."""
        if not self.errors:
            logger.info("Data validation passed")
            return

        logger.warning(f"Data validation found {len(self.errors)} errors")

        for i, error in enumerate(self.errors[:max_errors]):
            logger.warning(
                f"  [{i + 1}] Row {error.row_index}, Column '{error.column}': "
                f"{error.error_type} - {error.message}"
            )

        if len(self.errors) > max_errors:
            logger.warning(f"  ... and {len(self.errors) - max_errors} more errors")
