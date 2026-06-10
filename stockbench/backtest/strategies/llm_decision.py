"""
LLM Decision Strategy (for backtesting phase)

This module provides an LLM-based trading strategy `Strategy` that is called by the backtesting engine 
on a daily basis during backtesting:
Build features from factors/news/financials, call LLM for analysis and decision-making, generate buy/sell orders

Design objectives:
- Interact with the backtesting engine through a unified `on_bar(ctx)` interface, returning daily order list
- Control through configuration the news lookback window, feature window, etc.
"""
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)
from typing import Any, Dict, List
import pandas as pd

from stockbench.core.executor import decide_batch as unified_decide_batch
from stockbench.core import data_hub


class Strategy:
    """LLM-based backtesting strategy.

    Usage: Called by the backtesting engine on each backtesting day via `on_bar(ctx)` to get order list.

    Attribute descriptions:
    - cfg: Configuration dictionary related to strategy and backtesting
    - news_lookback_days: News lookback window days for feature construction
    - page_limit: News item retrieval limit
    - warmup_days: Historical lookback days needed for feature construction (e.g., moving averages, financials)
    - agent_mode: Agent mode, "multi" (multi-agent) or "single" (single-agent)
    - previous_decisions: Previous decision results for backward compatibility
    - decision_history: Long-term historical decision records, storing all historical decisions by date and symbol
    """
    def __init__(self, cfg: Dict) -> None:
        """Initialize strategy.

        Parameters:
        - cfg: Configuration dictionary containing risk/news/backtest/llm sub-configurations
        """
        self.cfg = cfg
        self.news_lookback_days = int((cfg or {}).get("news", {}).get("lookback_days", 7))
        self.page_limit = int((cfg or {}).get("news", {}).get("page_limit", 50))
        self.warmup_days = int((cfg or {}).get("backtest", {}).get("warmup_days", 60))
        # Agent mode: "dual" (dual-agent) or "single" (single-agent), default single-agent
        agents_mode = (cfg or {}).get("agents", {}).get("mode")
        self.agent_mode = str(agents_mode or "single").lower()
        
        # Debug: Detailed configuration parsing process
        logger.debug(f"[DEBUG] Agent mode configuration parsing:")
        logger.debug(f"  - agents.mode: {agents_mode}")
        logger.debug(f"  - Final agent_mode: {self.agent_mode}")
        
        # Store previous decision results for backward compatibility
        self.previous_decisions: Dict | None = None
        
        # Long-term historical decision record system
        # Structure: {symbol: [{"date": "YYYY-MM-DD", "decision": {...}, "meta": {...}}, ...]}
        self.decision_history: Dict[str, List[Dict]] = {}
        
        # Get historical record parameters from configuration
        history_cfg = (cfg or {}).get("backtest", {}).get("history", {})
        self.max_records_per_symbol = int(history_cfg.get("max_records_per_symbol", 10))
        self.max_history_days = int(history_cfg.get("max_history_days", 30))
        
        # Temporary storage for pending decisions (to be recorded after execution)
        self.pending_decisions: Dict[str, Dict] = {}
        self.pending_meta: Dict = {}
        self.f11_records: Dict[str, List[Dict[str, Any]]] = {}
        self.f11_weekly_buy_add_counts: Dict[str, int] = {}
        
        logger.debug(f"[DEBUG] Strategy initialization: Long-term historical record system enabled")
        logger.debug(f"[DEBUG] Strategy initialization: Maximum {self.max_records_per_symbol} historical records per symbol")
        logger.debug(f"[DEBUG] Strategy initialization: Maximum {self.max_history_days} days of historical records")
    
    def _add_decision_to_history(self, date: str, decisions: Dict[str, Dict], meta: Dict = None, clear_date_first: bool = False):
        """Add decision results to long-term historical records
        
        Args:
            date: Decision date in YYYY-MM-DD format
            decisions: Decision results dictionary
            meta: Meta information
            clear_date_first: Whether to clear existing records for this date first (override mechanism)
        """
        logger.info(f"=== Long-term Historical Record Save Started ===")
        logger.info(f"[HISTORY_SAVE] Starting to save decision records for date {date}")
        logger.debug(f"[HISTORY_SAVE] Input decisions type: {type(decisions)}")
        logger.debug(f"[HISTORY_SAVE] Input decisions keys: {list(decisions.keys()) if decisions else 'None'}")
        logger.debug(f"[HISTORY_SAVE] Input meta: {meta}")
        logger.debug(f"[HISTORY_SAVE] Clear date first: {clear_date_first}")
        
        if not decisions:
            logger.warning(f"[HISTORY_SAVE] Warning: No decision data to save")
            return
        
        # Override mechanism: Clear existing records for this date first
        if clear_date_first:
            logger.info(f"[HISTORY_SAVE] Override mode enabled, clearing existing records for date {date}")
            self._clear_decisions_for_date(date)
            
        # Extract decision records (excluding meta information)
        decision_records = {k: v for k, v in decisions.items() if k != "__meta__"}
        logger.info(f"[HISTORY_SAVE] Extracted decision records for {len(decision_records)} symbols")
        logger.debug(f"[HISTORY_SAVE] Decision record symbols: {list(decision_records.keys())}")
        
        # Historical record state before saving
        logger.debug(f"[HISTORY_SAVE] Historical record state before saving:")
        for symbol, records in self.decision_history.items():
            logger.debug(f"  - {symbol}: {len(records)} records")
            if records:
                latest = records[0]
                logger.debug(f"    Latest record: date={latest.get('date', 'N/A')}, action={latest.get('decision', {}).get('action', 'N/A')}")
        
        saved_count = 0
        for symbol, decision in decision_records.items():
            logger.debug(f"[HISTORY_SAVE] Processing symbol {symbol}:")
            logger.debug(f"  - Decision content: {decision}")
            
            if not isinstance(decision, dict):
                logger.warning(f"  - Skipping: Decision is not in dictionary format")
                continue
                
            # Ensure the historical record list for this symbol exists
            if symbol not in self.decision_history:
                self.decision_history[symbol] = []
                logger.debug(f"  - Created new historical record list")
            else:
                logger.debug(f"  - Existing historical record count: {len(self.decision_history[symbol])}")
            
            # Build historical record entry
            history_entry = {
                "date": date,
                "decision": decision.copy(),  # Copy decision content
                "meta": meta.copy() if meta else {}
            }
            logger.debug(f"  - Built historical record entry: {history_entry}")
            
            # Add to the beginning of historical record list (newest first)
            self.decision_history[symbol].insert(0, history_entry)
            logger.debug(f"  - Added to beginning of historical record list")
            
            # Limit the number of historical records per symbol
            if len(self.decision_history[symbol]) > self.max_records_per_symbol:
                removed_count = len(self.decision_history[symbol]) - self.max_records_per_symbol
                self.decision_history[symbol] = self.decision_history[symbol][:self.max_records_per_symbol]
                logger.info(f"[HISTORY_LIMIT] {symbol}: Cleaned {removed_count} old records, keeping latest {self.max_records_per_symbol} records")
            
            logger.debug(f"  - Historical record count after saving: {len(self.decision_history[symbol])}")
            saved_count += 1
        
        logger.info(f"=== Long-term Historical Record Save Completed ===")
        logger.info(f"[HISTORY_SAVE] Successfully saved decision records for {saved_count} symbols")
        logger.info(f"[HISTORY_SAVE] Current historical record statistics: Total {len(self.decision_history)} symbols have historical records")
        
        # Detailed post-save state
        for symbol, records in self.decision_history.items():
            logger.debug(f"[HISTORY_SAVE] {symbol}: {len(records)} historical records")
            if records:
                logger.debug(f"  - Latest record: date={records[0].get('date', 'N/A')}")
                latest_decision = records[0].get('decision', {})
                logger.debug(f"    action={latest_decision.get('action', 'N/A')}")
                logger.debug(f"    target_cash_amount={latest_decision.get('target_cash_amount', 'N/A')}")
                logger.debug(f"    confidence={latest_decision.get('confidence', 'N/A')}")
                
                if len(records) > 1:
                    logger.debug(f"  - Historical record timeline:")
                    for i, record in enumerate(records[:5]):  # Only show first 5 records
                        logger.debug(f"    {i+1}. {record.get('date', 'N/A')} - {record.get('decision', {}).get('action', 'N/A')}")
                    if len(records) > 5:
                        logger.debug(f"    ... {len(records) - 5} more records")
        
        logger.info(f"=== Long-term Historical Record Save Ended ===\n")
    
    def _get_decision_history_for_prompt(self, symbols: List[str] = None) -> Dict[str, List[Dict]]:
        """Get historical decision records for building prompts"""
        logger.info(f"\n=== Historical Record Building Started ===")
        logger.info(f"[HISTORY_BUILD] Starting to build historical decision records for prompt")
        logger.debug(f"[HISTORY_BUILD] Requested symbol count: {len(symbols) if symbols else 'all'}")
        logger.debug(f"[HISTORY_BUILD] Requested symbols: {symbols if symbols else 'all available symbols'}")
        
        history_for_prompt = {}
        
        # If no symbols specified, return all historical records
        target_symbols = symbols if symbols else list(self.decision_history.keys())
        logger.debug(f"[HISTORY_BUILD] Target symbols: {target_symbols}")
        logger.debug(f"[HISTORY_BUILD] Symbols in current long-term historical records: {list(self.decision_history.keys())}")
        
        found_count = 0
        for symbol in target_symbols:
            logger.debug(f"\n[HISTORY_BUILD] Processing symbol {symbol}:")
            
            if symbol in self.decision_history:
                # Convert historical record format to prompt-required format
                symbol_history = []
                original_records = self.decision_history[symbol]
                logger.debug(f"  - Found {len(original_records)} original historical records")
                
                for i, entry in enumerate(original_records):
                    decision = entry["decision"]
                    logger.debug(f"  - Processing record {i+1}:")
                    logger.debug(f"    Original date: {entry.get('date', 'N/A')}")
                    logger.debug(f"    Original decision: {decision}")
                    
                    history_record = {
                        "date": entry["date"],
                        "action": decision.get("action", "hold"),
                        "cash_change": decision.get("cash_change", 0.0),
                        "target_cash_amount": decision.get("target_cash_amount", 0.0),
                        "shares": decision.get("shares", 0.0),
                        "confidence": decision.get("confidence", 0.5)
                    }
                    logger.debug(f"    Converted record: {history_record}")
                    symbol_history.append(history_record)
                
                history_for_prompt[symbol] = symbol_history
                found_count += 1
                logger.debug(f"  - Successfully built {len(symbol_history)} historical records for prompt")
            else:
                logger.warning(f"  - Warning: Symbol {symbol} does not exist in long-term historical records")
                logger.debug(f"  - Will return empty historical records")
                history_for_prompt[symbol] = []
        
        logger.info(f"\n=== Historical Record Building Completed ===")
        logger.info(f"[HISTORY_BUILD] Successfully built historical records for {found_count} symbols")
        logger.info(f"[HISTORY_BUILD] Returned historical record statistics:")
        for symbol, records in history_for_prompt.items():
            logger.debug(f"  - {symbol}: {len(records)} records")
            if records:
                logger.debug(f"    Latest record: {records[0].get('date', 'N/A')} - {records[0].get('action', 'N/A')}")
                logger.debug(f"    Record time range: {records[-1].get('date', 'N/A')} to {records[0].get('date', 'N/A')}")
        
        logger.info(f"=== Historical Record Building Ended ===\n")
        return history_for_prompt
    
    def _cleanup_old_history(self, current_date: str):
        """Clean up expired historical records"""
        logger.info(f"\n=== Historical Record Cleanup Started ===")
        logger.info(f"[HISTORY_CLEANUP] Starting to clean up expired historical records")
        logger.debug(f"[HISTORY_CLEANUP] Current date: {current_date}")
        logger.debug(f"[HISTORY_CLEANUP] Maximum retention days: {self.max_history_days}")
        
        try:
            from datetime import datetime, timedelta
            current_dt = datetime.strptime(current_date, "%Y-%m-%d")
            cutoff_date = current_dt - timedelta(days=self.max_history_days)
            cutoff_date_str = cutoff_date.strftime("%Y-%m-%d")
            logger.debug(f"[HISTORY_CLEANUP] Cutoff date: {cutoff_date_str}")
            
            # State before cleanup
            logger.debug(f"[HISTORY_CLEANUP] Historical record state before cleanup:")
            total_records_before = 0
            for symbol, records in self.decision_history.items():
                logger.debug(f"  - {symbol}: {len(records)} records")
                total_records_before += len(records)
                if records:
                    oldest_date = records[-1].get('date', 'N/A')
                    newest_date = records[0].get('date', 'N/A')
                    logger.debug(f"    Time range: {oldest_date} to {newest_date}")
            logger.debug(f"  - Total: {total_records_before} records")
            
            cleaned_count = 0
            symbols_to_remove = []
            
            for symbol in list(self.decision_history.keys()):
                logger.debug(f"\n[HISTORY_CLEANUP] Processing symbol {symbol}:")
                original_count = len(self.decision_history[symbol])
                logger.debug(f"  - Original record count: {original_count}")
                
                # Filter out expired records
                original_records = self.decision_history[symbol]
                valid_records = [
                    entry for entry in original_records
                    if entry["date"] >= cutoff_date_str
                ]
                expired_records = [
                    entry for entry in original_records
                    if entry["date"] < cutoff_date_str
                ]
                
                logger.debug(f"  - Valid record count: {len(valid_records)}")
                logger.debug(f"  - Expired record count: {len(expired_records)}")
                
                if expired_records:
                    logger.debug(f"  - Expired record details:")
                    for i, record in enumerate(expired_records[:3]):  # Only show first 3 records
                        logger.debug(f"    {i+1}. {record.get('date', 'N/A')} - {record.get('decision', {}).get('action', 'N/A')}")
                    if len(expired_records) > 3:
                        logger.debug(f"    ... {len(expired_records) - 3} more expired records")
                
                # Update historical records
                self.decision_history[symbol] = valid_records
                expired_count = original_count - len(valid_records)
                cleaned_count += expired_count
                
                # Log cleanup results
                if expired_count > 0:
                    logger.info(f"[HISTORY_CLEANUP] {symbol}: Removed {expired_count} expired records (older than {cutoff_date_str}), {len(valid_records)} records remaining")
                
                # If a symbol has no historical records left, mark for deletion
                if not valid_records:
                    logger.info(f"[HISTORY_CLEANUP] {symbol}: No valid records left, removing symbol from history")
                    symbols_to_remove.append(symbol)
                    logger.debug(f"  - Mark for deletion: no valid records")
                else:
                    logger.debug(f"  - Retained record count: {len(valid_records)}")
                    oldest_valid = valid_records[-1].get('date', 'N/A')
                    newest_valid = valid_records[0].get('date', 'N/A')
                    logger.debug(f"  - Valid record time range: {oldest_valid} to {newest_valid}")
            
            # Delete symbols with no historical records
            for symbol in symbols_to_remove:
                del self.decision_history[symbol]
                logger.debug(f"[HISTORY_CLEANUP] Delete symbol {symbol}: no valid historical records")
            
            # State after cleanup
            logger.debug(f"\n[HISTORY_CLEANUP] Historical record state after cleanup:")
            total_records_after = 0
            for symbol, records in self.decision_history.items():
                logger.debug(f"  - {symbol}: {len(records)} records")
                total_records_after += len(records)
            logger.debug(f"  - Total: {total_records_after} records")
            
            if cleaned_count > 0:
                logger.debug(f"\n[HISTORY_CLEANUP] Cleanup completed: cleaned {cleaned_count} expired records")
                logger.debug(f"[HISTORY_CLEANUP] Record reduction: {total_records_before} -> {total_records_after}")
            else:
                logger.debug(f"\n[HISTORY_CLEANUP] Cleanup completed: no expired records to clean")
                
        except Exception as e:
            logger.error(f"[HISTORY_CLEANUP] Error: Historical record cleanup failed: {e}")
            import traceback
            logger.error(f"[HISTORY_CLEANUP] Error details: {traceback.format_exc()}")
        
        logger.info(f"=== Historical Record Cleanup Ended ===\n")
    
    def _clear_decisions_for_date(self, target_date: str):
        """Clear decision records for a specific date (used for retry mechanism)
        
        Args:
            target_date: Target date in YYYY-MM-DD format
        """
        logger.info(f"\n=== Clear Target Date Decision Records Started ===")
        logger.info(f"[DATE_CLEAR] Starting to clear decision records for date: {target_date}")
        
        cleared_symbols = []
        total_cleared_records = 0
        
        # Iterate through all symbols and clear records for the target date
        for symbol in list(self.decision_history.keys()):
            original_count = len(self.decision_history[symbol])
            logger.debug(f"[DATE_CLEAR] Processing symbol {symbol}: original record count = {original_count}")
            
            # Filter out records from the target date
            filtered_records = [
                record for record in self.decision_history[symbol]
                if record.get("date") != target_date
            ]
            
            cleared_count = original_count - len(filtered_records)
            if cleared_count > 0:
                self.decision_history[symbol] = filtered_records
                cleared_symbols.append(symbol)
                total_cleared_records += cleared_count
                logger.debug(f"[DATE_CLEAR] {symbol}: cleared {cleared_count} records for date {target_date}")
                
                # If no records remain for this symbol, delete the symbol
                if not filtered_records:
                    del self.decision_history[symbol]
                    logger.debug(f"[DATE_CLEAR] {symbol}: symbol deleted (no remaining records)")
            else:
                logger.debug(f"[DATE_CLEAR] {symbol}: no records found for date {target_date}")
        
        logger.info(f"\n=== Clear Target Date Decision Records Completed ===")
        logger.info(f"[DATE_CLEAR] Summary:")
        logger.info(f"  - Target date: {target_date}")
        logger.info(f"  - Symbols affected: {len(cleared_symbols)}")
        logger.info(f"  - Total records cleared: {total_cleared_records}")
        if cleared_symbols:
            logger.info(f"  - Affected symbols: {cleared_symbols}")
        logger.info(f"  - Remaining symbols with records: {len(self.decision_history)}")
        logger.info(f"=== Clear Target Date Decision Records Ended ===\n")
    
    def _build_previous_decisions_for_compatibility(self, current_date: str) -> Dict:
        """For backward compatibility, build previous_decisions format"""
        logger.info(f"\n=== Backward Compatibility Build Started ===")
        logger.info(f"[COMPATIBILITY_BUILD] Starting to build backward-compatible previous_decisions format")
        logger.debug(f"[COMPATIBILITY_BUILD] Current date: {current_date}")
        logger.debug(f"[COMPATIBILITY_BUILD] Long-term historical record status: {len(self.decision_history)} symbols")
        
        if not self.decision_history:
            logger.warning(f"[COMPATIBILITY_BUILD] Warning: no long-term historical records, returning None")
            logger.info(f"=== Backward Compatibility Build Ended ===\n")
            return None
            
        # Find the most recent decision date
        latest_date = None
        latest_decisions = {}
        
        logger.debug(f"[COMPATIBILITY_BUILD] Analyzing latest decision dates for all symbols:")
        for symbol, records in self.decision_history.items():
            if records:
                record_date = records[0]["date"]  # Latest record
                logger.debug(f"  - {symbol}: latest record date {record_date}")
                if latest_date is None or record_date > latest_date:
                    latest_date = record_date
                    logger.debug(f"    -> Updated to latest date: {latest_date}")
            else:
                logger.debug(f"  - {symbol}: no historical record")
        
        if latest_date:
            logger.debug(f"\n[COMPATIBILITY_BUILD] Determined latest decision date: {latest_date}")
            logger.debug(f"[COMPATIBILITY_BUILD] Building decision records for that date:")
            
            # Build previous_decisions format
            for symbol, records in self.decision_history.items():
                if records and records[0]["date"] == latest_date:
                    decision = records[0]["decision"]
                    latest_decisions[symbol] = decision
                    logger.debug(f"  - {symbol}: add decision record")
                    logger.debug(f"    action: {decision.get('action', 'N/A')}")
                    logger.debug(f"    target_cash_amount: {decision.get('target_cash_amount', 'N/A')}")
                    logger.debug(f"    confidence: {decision.get('confidence', 'N/A')}")
                else:
                    if records:
                        logger.debug(f"  - {symbol}: skip, latest record date {records[0]['date']} != {latest_date}")
                    else:
                        logger.debug(f"  - {symbol}: skip, no historical record")
            
            # Add meta information
            meta_info = {
                "date": latest_date,
                "calls": 1  # This might need to be obtained from actual calls
            }
            latest_decisions["__meta__"] = meta_info
            logger.debug(f"\n[COMPATIBILITY_BUILD] add meta information: {meta_info}")
            
            logger.debug(f"\n[COMPATIBILITY_BUILD] build completed: {len(latest_decisions)-1} symbols' decision records")
            logger.debug(f"[COMPATIBILITY_BUILD] returned previous_decisions structure:")
            for key, value in latest_decisions.items():
                if key != "__meta__":
                    logger.debug(f"  - {key}: {type(value)} - {value}")
                else:
                    logger.debug(f"  - {key}: {type(value)} - {value}")
        else:
            logger.warning(f"[COMPATIBILITY_BUILD] warning: no valid decision date found")
            latest_decisions = None
        
        logger.info(f"=== Backward Compatibility Build Ended ===\n")
        return latest_decisions if latest_decisions else None


    def _build_features_for_day(self, ctx) -> List[Dict]:
        """
        Build daily features: Get historical data, news, financials, etc., and build feature list.
        Optimization: Directly build new format features to avoid subsequent repeated conversions
        """
        features_list = []
        open_map = ctx["open_map"]
        datasets = ctx["datasets"]
        portfolio = ctx["portfolio"]
        
        # Get configuration parameters
        news_lookback_days = int(self.cfg.get("news", {}).get("lookback_days", 7))
        page_limit = int(self.cfg.get("news", {}).get("page_limit", 100))
        warmup_days = int(self.cfg.get("backtest", {}).get("warmup_days", 7))
        
        for symbol in open_map.keys():
            # Get historical data (for feature construction)
            start_date = ctx["date"] - pd.Timedelta(days=warmup_days + 5)  # Get 5 extra days as buffer
            end_date = ctx["date"]
            
            bars_day = datasets.get_day_bars(symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            
            # Get news data
            news_items = []
            try:
                # News fetching logic: let data_hub.py handle lookahead bias prevention
                # If making decisions on May 1st with lookback_days=3, should fetch news from April 28-30
                news_end_date = end_date  # Pass decision date directly, let get_news() handle bias prevention
                news_start_date = end_date - pd.Timedelta(days=self.news_lookback_days)  # Go back lookback days
                
                logger.debug(f"[DEBUG] News fetching parameter correction:")
                logger.debug(f"[DEBUG]   Decision date: {end_date.strftime('%Y-%m-%d')}")
                logger.debug(f"[DEBUG]   News fetching range: {news_start_date.strftime('%Y-%m-%d')} to {news_end_date.strftime('%Y-%m-%d')}")
                
                news_result = data_hub.get_news(
                    symbol, 
                    news_start_date.strftime("%Y-%m-%d"), 
                    news_end_date.strftime("%Y-%m-%d"),
                    limit=page_limit
                )
                if news_result is not None:
                    news_raw, _ = news_result
                else:
                    news_raw = []
                
                # Handle different news data formats
                if isinstance(news_raw, dict):
                    if "results" in news_raw and isinstance(news_raw["results"], list):
                        news_items = news_raw["results"]
                    elif "data" in news_raw and isinstance(news_raw["data"], list):
                        news_items = news_raw["data"]
                    else:
                        news_items = news_raw
                elif isinstance(news_raw, list):
                    news_items = news_raw
                else:
                    news_items = []
                
                # 🚨 Time filtering logic (consistent with fetching logic)
                if news_items:
                    valid_news = []
                    
                    logger.debug(f"[DEBUG] Start time filtering - news count: {len(news_items)}")
                    logger.debug(f"[DEBUG] Using time range consistent with fetching: {news_start_date.strftime('%Y-%m-%d')} to {news_end_date.strftime('%Y-%m-%d')}")
                    
                    for i, news in enumerate(news_items):
                        if not isinstance(news, dict):
                            logger.debug(f"[DEBUG] News #{i}: skip - not dictionary type")
                            continue
                            
                        news_time_str = news.get("published_utc") or news.get("published_date")
                        if not news_time_str:
                            logger.debug(f"[DEBUG] News #{i}: skip - no time field")
                            continue
                            
                        try:
                            news_time = pd.to_datetime(news_time_str, utc=True, errors="coerce")
                            if pd.isna(news_time):
                                logger.debug(f"[DEBUG] News #{i}: skip - time parsing failed: {news_time_str}")
                                continue
                                
                            from stockbench.core.data_hub import _normalize_timestamp_for_comparison
                            news_time_naive = _normalize_timestamp_for_comparison(news_time)
                            filter_start_naive = _normalize_timestamp_for_comparison(news_start_date)
                            # 🚨 Fix: Let news_end_date include the entire day, not just midnight
                            # Set end date to 23:59:59 of that day
                            news_end_date_eod = news_end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                            filter_end_naive = _normalize_timestamp_for_comparison(news_end_date_eod)
                            
                            logger.debug(f"[DEBUG] News #{i}: time comparison - news:{news_time_naive.strftime('%Y-%m-%d %H:%M')}, range:{filter_start_naive.strftime('%Y-%m-%d')} to {news_end_date.strftime('%Y-%m-%d')} 23:59")
                            
                            if filter_start_naive <= news_time_naive <= filter_end_naive:
                                valid_news.append(news)
                                logger.debug(f"[DEBUG] News #{i}: ✅ Passed time filtering")
                            else:
                                logger.debug(f"[DEBUG] News #{i}: ❌ Time out of range")
                        except Exception as e:
                            logger.debug(f"[DEBUG] News #{i}: Time processing exception: {e}")
                            continue
                    
                    news_items = valid_news
                    logger.debug(f"[DEBUG] Time filtering completed - remaining news count: {len(news_items)}")
                        
            except Exception as e:
                # Failed to get news
                import traceback
                traceback.print_exc()
            
            # Get financial data
            financials = []
            try:
                financials = data_hub.get_financials(symbol)
            except Exception as e:
                # Failed to get financial data
                pass
            
            # Get dividend and split data
            dividends = pd.DataFrame()
            splits = pd.DataFrame()
            try:
                dividends = data_hub.get_dividends(symbol)
                splits = data_hub.get_splits(symbol)
            except Exception as e:
                # Failed to get dividend/split data
                pass
            
            # Build market snapshot
            ref_price = open_map.get(symbol, 0.0)
            snapshot = {
                "symbol": symbol,
                "price": ref_price,
                "ts_utc": ctx["date"].strftime("%Y-%m-%dT00:00:00Z")
            }
            
            # Build symbol details
            details = {"ticker": symbol}
            
            # Build position state
            position = portfolio.positions.get(symbol)
            # Use unified price tools to calculate position value
            current_position_value = 0.0
            if position and hasattr(position, "shares") and position.shares:
                from stockbench.core.price_utils import calculate_position_value
                
                # Prepare fallback price
                fallback_price = ref_price or (bars_day["close"].iloc[-1] if not bars_day.empty and "close" in bars_day.columns else 100.0)
                
                try:
                    # Print debug info: check price data in ctx
                    if ctx:
                        open_map_keys = list(ctx.get("open_map", {}).keys())
                        open_price_map_keys = list(ctx.get("open_price_map", {}).keys())
                        logger.debug(f"[POSITION_VALUE_DEBUG] {symbol}: ctx.open_map has {len(open_map_keys)} stocks: {open_map_keys[:5]}")
                        logger.debug(f"[POSITION_VALUE_DEBUG] {symbol}: ctx.open_price_map has {len(open_price_map_keys)} stocks: {open_price_map_keys[:5]}")
                        if symbol in ctx.get("open_map", {}):
                            logger.debug(f"[POSITION_VALUE_DEBUG] {symbol}: found price in open_map = {ctx['open_map'][symbol]}")
                        if symbol in ctx.get("open_price_map", {}):
                            logger.debug(f"[POSITION_VALUE_DEBUG] {symbol}: found price in open_price_map = {ctx['open_price_map'][symbol]}")
                    
                    current_position_value = calculate_position_value(
                        symbol=symbol,
                        shares=position.shares,
                        ctx=ctx,
                        portfolio=None,  # No portfolio object here
                        position_avg_price=getattr(position, 'avg_price', None)
                    )
                    
                    # If unified tool also fails, use original fallback logic
                    if current_position_value == 0.0 and fallback_price and fallback_price > 0:
                        current_position_value = float(position.shares * fallback_price)
                        logger.info(f"[POSITION_VALUE] {symbol}: {position.shares:.2f} shares × {fallback_price:.4f} (final_fallback) = {current_position_value:.2f}")
                        
                except Exception as e:
                    current_position_value = 0.0
                    logger.warning(f"[POSITION_VALUE] {symbol}: Failed to calculate position value: {e}")
                    # Print more detailed error information
                    logger.warning(f"[POSITION_VALUE_DEBUG] {symbol}: ctx keys = {list(ctx.keys()) if ctx else 'None'}")
                    import traceback
                    logger.warning(f"[POSITION_VALUE_DEBUG] {symbol}: detailed error = {traceback.format_exc()}")
            
            # If no position object, create a default position state
            if position is None:
                # Create default position state: 0 shares, 0 avg price, 0 holding days
                position = type('Position', (), {
                    'shares': 0,
                    'avg_price': 0.0,
                    'holding_days': 0
                })()
            

            holding_days = int(getattr(position, "holding_days", 0) or 0) if position else 0
            position_state = {
                "current_position_value": current_position_value,  # Use amount instead of percentage
                "holding_days": holding_days,
                "shares": round(float(getattr(position, "shares", 0) or 0), 2)
            }
            
            # Convert news_items to simple title+description format
            simple_news_list = []
            if news_items:
                for news_item in news_items:
                    if isinstance(news_item, dict):
                        title = news_item.get("title", "")
                        description = news_item.get("description", "")
                        if title:
                            # Format: "title - description" if both exist, otherwise just title
                            if description and description.strip():
                                news_text = f"{title} - {description}"
                            else:
                                news_text = title
                            simple_news_list.append(news_text)
                    elif isinstance(news_item, str) and news_item.strip():
                        simple_news_list.append(news_item)
            
            if not simple_news_list:
                simple_news_list = ["No news available"]
            
            # Build historical close_7d price series correctly
            close_7d = []
            try:
                if not bars_day.empty and "close" in bars_day.columns:
                    # Sort data by date and remove duplicates
                    if "date" in bars_day.columns:
                        bars_clean = bars_day.drop_duplicates(subset=["date"], keep="last").sort_values("date")
                    else:
                        bars_clean = bars_day.drop_duplicates(keep="last")
                    
                    # Get closing prices from the past 7 days (excluding current day)
                    if len(bars_clean) > 1:
                        # Exclude current day and take previous 7 days
                        available_historical_data = len(bars_clean) - 1  # Exclude current day
                        if available_historical_data > 0:
                            start_idx = max(0, available_historical_data - 7)
                            end_idx = available_historical_data  # Exclude current day
                            close_data = bars_clean["close"].iloc[start_idx:end_idx]
                            
                            # Convert to float list
                            for val in close_data:
                                if val is not None and not pd.isna(val):
                                    close_7d.append(float(val))
                                else:
                                    close_7d.append(0.0)
                    
                    # Pad with 0s if insufficient data
                    if len(close_7d) < 7:
                        close_7d = [0.0] * (7 - len(close_7d)) + close_7d
                        
                    # Ensure exactly 7 elements
                    close_7d = close_7d[-7:]  # Take last 7 elements
                        
                else:
                    # No historical data available
                    close_7d = [0.0] * 7
                    
            except Exception as e:
                logger.warning(f"Error building close_7d for {symbol}: {e}")
                close_7d = [0.0] * 7

            f11_market_context = self._compute_f11_market_context(bars_day)

            # Build minimal features structure
            fi = {
                "symbol": symbol,
                "features": {
                    "market_data": {"ticker": symbol, "open": ref_price, "close_7d": close_7d},
                    "news_events": {"top_k_events": simple_news_list},
                    "position_state": position_state,
                    "f11_market_context": f11_market_context,
                },
                "market_ctx": {"daily_drawdown_pct": float(ctx.get("daily_drawdown_pct") or 0.0)}
            }
            
            features_list.append(fi)
        
        return features_list

    def _f11_module_cfg(self, name: str) -> Dict:
        modules = (self.cfg or {}).get("f11_modules") or (self.cfg or {}).get("modules") or {}
        return modules.get(name, {}) or {}

    def _f11_enabled(self, name: str) -> bool:
        return bool(self._f11_module_cfg(name).get("enabled", False))

    def _any_f11_enabled(self, *names: str) -> bool:
        return any(self._f11_enabled(name) for name in names)

    def _safe_float(self, value, default: float = 0.0) -> float:
        try:
            result = float(value)
            if math.isfinite(result):
                return result
        except (TypeError, ValueError):
            pass
        return default

    def _record_f11(self, module_name: str, record: Dict[str, Any]) -> None:
        self.f11_records.setdefault(module_name, []).append(record)

    def _f11_required_fundamental_fields(self) -> List[str]:
        return [
            "revenue_growth",
            "earnings_growth",
            "margin_trend",
            "debt_or_leverage",
            "cashflow_quality",
            "valuation_metric",
            "analyst_revision_or_guidance",
        ]

    def _f11_reliability_score(self, features: Dict) -> Dict[str, Any]:
        fundamental = features.get("fundamental_data") or {}
        fields = self._f11_required_fundamental_fields()
        missing_count = sum(1 for field in fields if fundamental.get(field) in (None, "", "unknown"))
        timestamp = (
            fundamental.get("latest_fundamental_timestamp")
            or fundamental.get("timestamp")
            or fundamental.get("as_of_date")
            or fundamental.get("filing_date")
            or fundamental.get("period_of_report_date")
        )
        score = 1.0
        data_age_days = None
        if not timestamp:
            score = min(score, 0.2)
        else:
            try:
                data_age_days = (pd.Timestamp.utcnow().tz_localize(None) - pd.Timestamp(str(timestamp)[:10])).days
            except Exception:
                data_age_days = None
                score = min(score, 0.2)
        if data_age_days is not None:
            if data_age_days <= 45:
                pass
            elif data_age_days <= 90:
                score -= 0.2
            elif data_age_days <= 180:
                score -= 0.4
            else:
                score -= 0.6
        missing_penalty = min(0.1 * missing_count, 0.4)
        score -= missing_penalty
        contradiction = bool(fundamental.get("contradiction_flag", False))
        if contradiction:
            score -= 0.3
        score = min(1.0, max(0.0, score))
        return {
            "latest_fundamental_timestamp": timestamp,
            "data_age_days": data_age_days,
            "has_required_fundamental_fields": missing_count == 0,
            "missing_required_field_count": missing_count,
            "contradiction_flag": contradiction,
            "reliability_score": score,
        }

    def _f11_market(self, features: Dict) -> Dict[str, float]:
        return features.get("f11_market_context") or {}

    def _f11_return_5d(self, features: Dict) -> float:
        return self._safe_float(self._f11_market(features).get("return_5d"))

    def _f11_return_20d(self, features: Dict) -> float:
        return self._safe_float(self._f11_market(features).get("return_20d"))

    def _f11_position_weight(self, current_value: float, ctx: Dict) -> float:
        total = self._safe_float(ctx.get("equity_for_sizing"))
        if total <= 0:
            pf = ctx.get("portfolio")
            total = self._safe_float(getattr(pf, "cash", 0.0)) if pf else 0.0
            if pf:
                total += sum(
                    self._safe_float(getattr(pos, "shares", 0.0)) * 100.0
                    for pos in getattr(pf, "positions", {}).values()
                )
        return current_value / total if total > 0 else 0.0

    def _f11_news_direction(self, features: Dict) -> int:
        events = ((features.get("news_events") or {}).get("top_k_events") or [])
        text = " ".join(str(item).lower() for item in events)
        if not text or "no news" in text:
            return 0
        positive_words = ["beat", "upgrade", "growth", "strong", "positive", "raises", "surge", "profit"]
        negative_words = ["miss", "downgrade", "weak", "negative", "risk", "fall", "lawsuit", "cut"]
        pos = sum(word in text for word in positive_words)
        neg = sum(word in text for word in negative_words)
        if pos > neg:
            return 1
        if neg > pos:
            return -1
        return 0

    def _f11_fundamental_direction(self, features: Dict) -> int:
        fundamental = features.get("fundamental_data") or {}
        score = self._safe_float(fundamental.get("fundamental_score"), 0.0)
        signal = str(fundamental.get("signal", "") or fundamental.get("direction", "")).lower()
        if score > 0.1 or "bull" in signal or "positive" in signal:
            return 1
        if score < -0.1 or "bear" in signal or "negative" in signal:
            return -1
        return 0

    def _f11_signal_conflict(self, features: Dict, pnl_pct: float) -> Dict[str, Any]:
        ret5 = self._f11_return_5d(features)
        ret20 = self._f11_return_20d(features)
        momentum = 1 if ret5 > 0 and ret20 > 0 else (-1 if ret5 < 0 and ret20 < 0 else 0)
        pnl_dir = 1 if pnl_pct > 0 else (-1 if pnl_pct < 0 else 0)
        signals = {
            "fundamental_direction": self._f11_fundamental_direction(features),
            "momentum_direction": momentum,
            "news_direction": self._f11_news_direction(features),
            "position_pnl_direction": pnl_dir,
        }
        nonzero = [value for value in signals.values() if value != 0]
        agreement = None
        if len(nonzero) >= 2:
            agreement = max(nonzero.count(1), nonzero.count(-1)) / len(nonzero)
        return {
            "nonzero_signal_count": len(nonzero),
            "signal_values": signals,
            "agreement_score": agreement,
        }

    def _f11_forward_return(self, symbol: str, ctx: Dict, start_date: str, horizon_days: int = 5) -> float | None:
        try:
            start = pd.Timestamp(start_date)
            end = start + pd.Timedelta(days=horizon_days + 10)
            bars = ctx["datasets"].get_day_bars(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
            if bars is None or bars.empty or "close" not in bars.columns:
                return None
            if "date" in bars.columns:
                bars = bars.drop_duplicates(subset=["date"], keep="last").sort_values("date")
            closes = [self._safe_float(v) for v in bars["close"].tolist() if self._safe_float(v) > 0]
            if len(closes) <= horizon_days:
                return None
            return closes[horizon_days] / closes[0] - 1.0
        except Exception:
            return None

    def _f11_universe_median_forward_return(self, ctx: Dict, start_date: str, horizon_days: int = 5) -> float:
        vals = []
        for symbol in (ctx.get("symbols") or ctx.get("open_map", {}).keys()):
            value = self._f11_forward_return(symbol, ctx, start_date, horizon_days)
            if value is not None:
                vals.append(value)
        return float(pd.Series(vals).median()) if vals else 0.0

    def _f11_failed_recent_buy_add(self, symbol: str, current_date: str, ctx: Dict) -> Dict[str, Any]:
        current = pd.Timestamp(current_date)
        for record in self.decision_history.get(symbol, []):
            decision = record.get("decision", {}) or {}
            action = str(decision.get("action", "")).lower()
            if action != "increase":
                continue
            date = record.get("date")
            try:
                days = (current - pd.Timestamp(date)).days
            except Exception:
                continue
            if days < 5 or days > 10:
                continue
            fwd = self._f11_forward_return(symbol, ctx, date, 5)
            median = self._f11_universe_median_forward_return(ctx, date, 5)
            rel = None if fwd is None else fwd - median
            failed = fwd is not None and (fwd < -0.02 or rel < -0.02)
            if failed:
                return {
                    "failed_recent_buy_add": True,
                    "failed_trade_date": date,
                    "failed_trade_5d_forward_return": fwd,
                    "failed_trade_relative_5d_return": rel,
                }
        return {
            "failed_recent_buy_add": False,
            "failed_trade_date": None,
            "failed_trade_5d_forward_return": None,
            "failed_trade_relative_5d_return": None,
        }

    def _compute_f11_market_context(self, bars_day: pd.DataFrame) -> Dict[str, float]:
        try:
            if bars_day is None or bars_day.empty or "close" not in bars_day.columns:
                return {"return_1d": 0.0, "return_5d": 0.0, "return_20d": 0.0}
            df = bars_day.copy()
            if "date" in df.columns:
                df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date")
            closes = [self._safe_float(v) for v in df["close"].tolist() if self._safe_float(v) > 0]
            if len(closes) > 1:
                closes = closes[:-1] if len(closes) > 2 else closes
            last = closes[-1] if closes else 0.0
            def ret(days: int) -> float:
                if last <= 0 or len(closes) <= days or closes[-days - 1] <= 0:
                    return 0.0
                return last / closes[-days - 1] - 1.0
            return {"return_1d": ret(1), "return_5d": ret(5), "return_20d": ret(20)}
        except Exception as exc:
            logger.warning(f"[F11] failed to compute market context: {exc}")
            return {"return_1d": 0.0, "return_5d": 0.0, "return_20d": 0.0}

    def _position_pnl_pct(self, symbol: str, ctx: Dict, open_map: Dict) -> float:
        pos = ctx["portfolio"].positions.get(symbol)
        if not pos or self._safe_float(getattr(pos, "shares", 0.0)) <= 0:
            return 0.0
        avg_price = self._safe_float(getattr(pos, "avg_price", 0.0))
        ref_px = self._safe_float(open_map.get(symbol))
        if avg_price <= 0 or ref_px <= 0:
            return 0.0
        return ref_px / avg_price - 1.0

    def _decision_reason_text(self, decision: Dict) -> str:
        reasons = decision.get("reasons", "")
        if isinstance(reasons, list):
            reasons = " ".join(str(v) for v in reasons)
        return str(reasons or decision.get("reason", "") or "").lower()

    def _is_protective_sell_reason(self, decision: Dict, extra_keywords: List[str] | None = None) -> bool:
        text = self._decision_reason_text(decision)
        keywords = extra_keywords or []
        keywords = keywords + ["risk", "drawdown", "stop-loss", "negative catalyst", "reduce risk", "deteriorat"]
        return any(keyword.lower() in text for keyword in keywords)

    def _last_action_days(self, symbol: str, current_date: str, actions: set[str]) -> int | None:
        records = self.decision_history.get(symbol, [])
        current = pd.Timestamp(current_date)
        for record in records:
            decision = record.get("decision", {}) or {}
            action = str(decision.get("action", "")).lower()
            if action not in actions:
                continue
            try:
                days = (current - pd.Timestamp(record.get("date"))).days
                return max(days, 0)
            except Exception:
                return None
        return None

    def _attach_f11_pre_decision_context(self, features_list: List[Dict], ctx: Dict) -> List[Dict]:
        if not features_list:
            return features_list

        use_rs = self._f11_enabled("I5_UNIVERSE_RELATIVE_STRENGTH_CONTEXT")
        use_drawdown = self._f11_enabled("R6_DRAWDOWN_CONTEXT_PROMPT")
        use_f11f_warning = self._f11_enabled("F11F_v2_PROMPT_WARNING_ONLY")
        use_f11k_warning = self._f11_enabled("F11K_v3_PROMPT_WARNING_ONLY")
        if not (use_rs or use_drawdown or use_f11f_warning or use_f11k_warning):
            return features_list

        if use_rs:
            returns_by_lb: Dict[str, Dict[str, float]] = {lb: {} for lb in ("1d", "5d", "20d")}
            for item in features_list:
                symbol = item.get("symbol")
                market = ((item.get("features") or {}).get("f11_market_context") or {})
                for lb in returns_by_lb:
                    returns_by_lb[lb][symbol] = self._safe_float(market.get(f"return_{lb}"))
            medians = {
                lb: pd.Series(values).median() if values else 0.0
                for lb, values in returns_by_lb.items()
            }
            ranks = {
                lb: pd.Series(values).rank(pct=True).to_dict() if values else {}
                for lb, values in returns_by_lb.items()
            }
            triggered = 0
            for item in features_list:
                symbol = item.get("symbol")
                features = item.setdefault("features", {})
                market = features.get("f11_market_context") or {}
                rank_5d = self._safe_float(ranks["5d"].get(symbol), 0.5)
                if rank_5d >= 0.75:
                    bucket = "top_quartile"
                elif rank_5d >= 0.5:
                    bucket = "above_median"
                elif rank_5d <= 0.25:
                    bucket = "bottom_quartile"
                else:
                    bucket = "below_median"
                context = {
                    "return_1d": self._safe_float(market.get("return_1d")),
                    "return_5d": self._safe_float(market.get("return_5d")),
                    "return_20d": self._safe_float(market.get("return_20d")),
                    "relative_5d": self._safe_float(market.get("return_5d")) - self._safe_float(medians["5d"]),
                    "relative_20d": self._safe_float(market.get("return_20d")) - self._safe_float(medians["20d"]),
                    "rank_5d_pct": rank_5d,
                    "rank_20d_pct": self._safe_float(ranks["20d"].get(symbol), 0.5),
                    "rank_bucket": bucket,
                    "prompt_note": f"{symbol} universe relative strength bucket: {bucket}; compare absolute moves with universe median before increasing exposure.",
                }
                features.setdefault("f11_context", {})["universe_relative_strength_context"] = context
                triggered += 1
            logger.info(f"[F11_I5_REL_STRENGTH] context_added={triggered}, total_symbols={len(features_list)}")

        if use_drawdown:
            cfg = self._f11_module_cfg("R6_DRAWDOWN_CONTEXT_PROMPT")
            moderate = self._safe_float(cfg.get("moderate_drawdown", -0.05), -0.05)
            severe = self._safe_float(cfg.get("severe_drawdown", -0.08), -0.08)
            raw_drawdown = self._safe_float(ctx.get("daily_drawdown_pct") or ctx.get("drawdown") or 0.0)
            drawdown = raw_drawdown / 100.0 if raw_drawdown < -1.0 else raw_drawdown
            if drawdown <= severe:
                level = "severe"
                note = "Portfolio drawdown is severe. Be selective with new buy/add; prioritize risk control and avoid averaging down weak positions."
            elif drawdown <= moderate:
                level = "moderate"
                note = "Portfolio drawdown is moderate. Avoid adding to underperformers without clear confirmation."
            else:
                level = "normal"
                note = ""
            for item in features_list:
                features = item.setdefault("features", {})
                features.setdefault("f11_context", {})["portfolio_drawdown_context"] = {
                    "current_drawdown": drawdown,
                    "level": level,
                    "prompt_note": note,
                }
            logger.info(f"[F11_R6_DRAWDOWN_CONTEXT] level={level}, drawdown={drawdown:.4f}, context_added={bool(note)}")

        if use_f11f_warning:
            added = 0
            for item in features_list:
                features = item.setdefault("features", {})
                diag = self._f11_reliability_score(features)
                if diag["reliability_score"] < 0.5:
                    features.setdefault("f11_context", {})["fundamental_reliability_warning"] = {
                        **diag,
                        "prompt_note": "Fundamental data reliability is low or stale; avoid relying on fundamentals for this BUY/ADD unless other evidence is strong.",
                    }
                    added += 1
            logger.info(f"[F11F_V2_PROMPT_WARNING] warning_context_added={added}, total_symbols={len(features_list)}")

        if use_f11k_warning:
            current_date = ctx["date"].strftime("%Y-%m-%d")
            added = 0
            for item in features_list:
                symbol = item.get("symbol")
                features = item.setdefault("features", {})
                failed = self._f11_failed_recent_buy_add(symbol, current_date, ctx)
                pnl = self._position_pnl_pct(symbol, ctx, ctx.get("open_map", {}))
                weak = pnl < 0 or self._f11_return_5d(features) < 0 or self._f11_return_20d(features) < 0
                improved = self._f11_return_5d(features) > 0 and pnl >= 0
                if failed["failed_recent_buy_add"] and weak and not improved:
                    features.setdefault("f11_context", {})["loser_cooldown_warning"] = {
                        **failed,
                        "weak_current_state": weak,
                        "improved_state": improved,
                        "prompt_note": "Recent similar BUY/ADD in this symbol had poor short-term outcome and current state remains weak; avoid repeating the same entry unless evidence has improved.",
                    }
                    added += 1
            logger.info(f"[F11K_V3_PROMPT_WARNING] warning_context_added={added}, total_symbols={len(features_list)}")

        return features_list

    def _log_f11_dryruns(self, features_list: List[Dict], decisions_map: Dict, ctx: Dict) -> None:
        if self._f11_enabled("F11E_v2_NEWS_PRICE_CONFLICT_DRYRUN"):
            news_available = 0
            conflicts = 0
            for item in features_list:
                symbol = item.get("symbol")
                features = item.get("features", {})
                decision = decisions_map.get(symbol, {}) if isinstance(decisions_map, dict) else {}
                action = str(decision.get("action", "hold")).lower()
                news_dir = self._f11_news_direction(features)
                if news_dir != 0:
                    news_available += 1
                ret1 = self._safe_float(self._f11_market(features).get("return_1d"))
                ret5 = self._f11_return_5d(features)
                conflict = (
                    (news_dir > 0 and action == "increase" and ret1 <= 0 and ret5 <= 0)
                    or (news_dir < 0 and action == "increase" and (ret1 < 0 or ret5 < 0))
                    or (news_dir < 0 and action in {"decrease", "close"} and ret1 >= 0 and ret5 >= 0)
                )
                conflicts += int(conflict)
                if conflict:
                    logger.info(f"[F11E_V2_NEWS_PRICE_DRYRUN] conflict symbol={symbol}, action={action}, news_dir={news_dir}, ret1={ret1:.4f}, ret5={ret5:.4f}")
            logger.info(f"[F11E_V2_NEWS_PRICE_DRYRUN] news_available_count={news_available}, total_conflict_count={conflicts}")

        if self._f11_enabled("F11C_v2_BAD_ENTRY_MEMORY_DRYRUN"):
            current_date = ctx["date"].strftime("%Y-%m-%d")
            created = 0
            retrieved = 0
            for symbol, records in self.decision_history.items():
                for record in records:
                    date = record.get("date")
                    action = str((record.get("decision") or {}).get("action", "")).lower()
                    if action != "increase":
                        continue
                    try:
                        days = (pd.Timestamp(current_date) - pd.Timestamp(date)).days
                    except Exception:
                        continue
                    if days < 5:
                        continue
                    fwd = self._f11_forward_return(symbol, ctx, date, 5)
                    rel = None if fwd is None else fwd - self._f11_universe_median_forward_return(ctx, date, 5)
                    if fwd is not None and (fwd < -0.02 or rel < -0.02):
                        created += 1
                        if symbol in decisions_map and str(decisions_map[symbol].get("action", "")).lower() == "increase":
                            retrieved += 1
                            logger.info(f"[F11C_V2_BAD_ENTRY_DRYRUN] retrieved symbol={symbol}, memory_date={date}, fwd5={fwd:.4f}, rel5={rel:.4f}")
                        break
            logger.info(f"[F11C_V2_BAD_ENTRY_DRYRUN] memory_created_count={created}, memory_retrieved_count={retrieved}")

    def _f11_size_multiplier(
        self,
        symbol: str,
        action: str,
        current_value: float,
        target_value: float,
        decision: Dict,
        features: Dict,
        ctx: Dict,
        open_map: Dict,
    ) -> float:
        multiplier = 1.0
        delta = target_value - current_value
        confidence = self._safe_float(decision.get("confidence", 0.5), 0.5)
        current_date = ctx["date"].strftime("%Y-%m-%d")
        is_buy_add = delta > 0
        is_sell_reduce = delta < 0
        action_label = "ADD" if is_buy_add and current_value > 0 else ("BUY" if is_buy_add else ("SELL" if is_sell_reduce else "HOLD"))

        if self._f11_enabled("F11F_v2_FUNDAMENTAL_RELIABILITY_HAIRCUT_ONLY") and is_buy_add:
            diag = self._f11_reliability_score(features)
            score = self._safe_float(diag.get("reliability_score"), 1.0)
            module_multiplier = 1.0
            if score < 0.3:
                module_multiplier = 0.5 if action_label == "ADD" else 0.7
            elif score < 0.5:
                module_multiplier = 0.7 if action_label == "ADD" else 0.85
            multiplier = min(multiplier, module_multiplier)
            logger.info(
                f"[F11F_V2_RELIABILITY_HAIRCUT] {symbol}: action={action_label}, score={score:.3f}, "
                f"missing={diag.get('missing_required_field_count')}, multiplier={module_multiplier:.2f}"
            )

        if self._f11_enabled("F11K_v3_LOSER_COOLDOWN_HAIRCUT_ONLY") and is_buy_add:
            failed = self._f11_failed_recent_buy_add(symbol, current_date, ctx)
            pnl = self._position_pnl_pct(symbol, ctx, open_map)
            ret5 = self._f11_return_5d(features)
            ret20 = self._f11_return_20d(features)
            weak = pnl < 0 or ret5 < 0 or ret20 < 0
            improved = ret5 > 0 and pnl >= 0
            triggered = bool(failed["failed_recent_buy_add"] and weak and not improved)
            module_multiplier = 1.0
            rebound_exception = False
            if triggered:
                module_multiplier = 0.5 if action_label == "ADD" else 0.7
                if ret5 > 0.03 and ret20 > 0:
                    module_multiplier = max(module_multiplier, 0.85)
                    rebound_exception = True
            multiplier = min(multiplier, module_multiplier)
            logger.info(
                f"[F11K_V3_LOSER_COOLDOWN] {symbol}: action={action_label}, failed={failed['failed_recent_buy_add']}, "
                f"weak={weak}, improved={improved}, rebound_exception={rebound_exception}, multiplier={module_multiplier:.2f}"
            )

        if self._f11_enabled("F11G_v2_SIGNAL_CONFLICT_HAIRCUT_ONLY") and is_buy_add:
            diag = self._f11_signal_conflict(features, self._position_pnl_pct(symbol, ctx, open_map))
            agreement = diag.get("agreement_score")
            module_multiplier = 1.0
            if agreement is not None:
                if agreement < 0.4:
                    module_multiplier = 0.5 if action_label == "ADD" else 0.7
                elif agreement < 0.6:
                    module_multiplier = 0.8 if action_label == "ADD" else 0.9
            multiplier = min(multiplier, module_multiplier)
            logger.info(
                f"[F11G_V2_SIGNAL_CONFLICT] {symbol}: action={action_label}, nonzero={diag['nonzero_signal_count']}, "
                f"agreement={agreement}, multiplier={module_multiplier:.2f}, signals={diag['signal_values']}"
            )

        if self._f11_enabled("F11J_v2_CROWDING_LOSER_ADD_ONLY") and is_buy_add and current_value > 0:
            position_weight = self._f11_position_weight(current_value, ctx)
            pnl = self._position_pnl_pct(symbol, ctx, open_map)
            ret5 = self._f11_return_5d(features)
            ret20 = self._f11_return_20d(features)
            weak = pnl < 0 or ret5 < 0 or ret20 < 0
            strong_winner_exception = position_weight > 0.12 and pnl > 0 and ret20 > 0
            module_multiplier = 1.0
            if position_weight > 0.08 and weak:
                if position_weight > 0.12:
                    module_multiplier = 0.3
                elif position_weight > 0.10:
                    module_multiplier = 0.5
                else:
                    module_multiplier = 0.7
                if strong_winner_exception:
                    module_multiplier = max(module_multiplier, 0.7)
            multiplier = min(multiplier, module_multiplier)
            logger.info(
                f"[F11J_V2_CROWDING_LOSER] {symbol}: weight={position_weight:.4f}, pnl={pnl:.4f}, "
                f"ret5={ret5:.4f}, ret20={ret20:.4f}, weak={weak}, strong_exception={strong_winner_exception}, "
                f"multiplier={module_multiplier:.2f}"
            )

        if self._f11_enabled("F11L_v2_SOFT_WEEKLY_BUY_ADD_THROTTLE") and is_buy_add:
            cfg = self._f11_module_cfg("F11L_v2_SOFT_WEEKLY_BUY_ADD_THROTTLE")
            week_id = pd.Timestamp(current_date).strftime("%G-W%V")
            before = int(self.f11_weekly_buy_add_counts.get(week_id, 0))
            budget = int(cfg.get("weekly_buy_add_budget", 10))
            module_multiplier = 1.0
            if before > budget:
                module_multiplier = 0.4 if confidence < 0.5 else 0.8
            multiplier = min(multiplier, module_multiplier)
            logger.info(
                f"[F11L_V2_WEEKLY_THROTTLE] {symbol}: week={week_id}, before={before}, budget={budget}, "
                f"confidence={confidence:.2f}, multiplier={module_multiplier:.2f}"
            )

        if self._f11_enabled("R2_CONFIDENCE_WEIGHTED_SIZING") and abs(delta) > 0:
            module_multiplier = 1.0
            if delta > 0:
                is_add = current_value > 0
                if is_add:
                    module_multiplier = 0.3 if confidence < 0.4 else (0.8 if confidence < 0.7 else 1.0)
                else:
                    module_multiplier = 0.5 if confidence < 0.4 else (1.0 if confidence < 0.7 else 1.2)
            elif delta < 0:
                module_multiplier = 0.5 if confidence < 0.4 else 1.0
            multiplier *= module_multiplier
            logger.info(f"[F11_R2_CONF_SIZE] {symbol}: confidence={confidence:.2f}, multiplier={module_multiplier:.2f}")

        if self._f11_enabled("R4_STATE_DEPENDENT_COOLDOWN") and abs(delta) > 0:
            cfg = self._f11_module_cfg("R4_STATE_DEPENDENT_COOLDOWN")
            cooldowns = cfg.get("cooldowns", {}) or {}
            category = None
            days_since = None
            active = False
            module_multiplier = 1.0
            if delta > 0:
                if current_value > 0:
                    pnl = self._position_pnl_pct(symbol, ctx, open_map)
                    category = "add_to_loser" if pnl < 0 else "add_to_winner"
                    days_since = self._last_action_days(symbol, current_date, {"increase"})
                else:
                    category = "new_buy_after_sell"
                    days_since = self._last_action_days(symbol, current_date, {"decrease", "close"})
                limit = int(cooldowns.get(category, 7 if category == "add_to_loser" else 5))
                active = days_since is not None and days_since < limit
                if active:
                    module_multiplier = self._safe_float(cfg.get("buy_add_cooldown_multiplier", 0.5), 0.5)
            elif delta < 0 and not self._is_protective_sell_reason(decision, cfg.get("protective_sell_keywords", [])):
                category = "sell_after_buy"
                days_since = self._last_action_days(symbol, current_date, {"increase"})
                limit = int(cooldowns.get(category, 5))
                active = days_since is not None and days_since < limit
                if active:
                    module_multiplier = self._safe_float(cfg.get("sell_cooldown_multiplier", 0.7), 0.7)
            multiplier *= module_multiplier
            logger.info(
                f"[F11_R4_STATE_COOLDOWN] {symbol}: category={category}, days_since={days_since}, "
                f"active={active}, multiplier={module_multiplier:.2f}"
            )

        if self._f11_enabled("R7_SOFT_WINNER_HOLDING_FRICTION") and delta < 0:
            cfg = self._f11_module_cfg("R7_SOFT_WINNER_HOLDING_FRICTION")
            min_holding_days = int(cfg.get("min_holding_days", 5))
            high_conf = self._safe_float(cfg.get("high_confidence_override", 0.8), 0.8)
            holding_days = int(((features.get("position_state") or {}).get("holding_days", 0)) or 0)
            pnl = self._position_pnl_pct(symbol, ctx, open_map)
            applies = (
                pnl > 0
                and holding_days < min_holding_days
                and confidence < high_conf
                and not self._is_protective_sell_reason(decision, cfg.get("risk_keywords", []))
            )
            module_multiplier = self._safe_float(cfg.get("sell_size_multiplier", 0.5), 0.5) if applies else 1.0
            multiplier *= module_multiplier
            logger.info(
                f"[F11_R7_WINNER_FRICTION] {symbol}: pnl={pnl:.4f}, holding_days={holding_days}, "
                f"applied={applies}, multiplier={module_multiplier:.2f}"
            )

        if multiplier > 1.0 + 1e-9:
            raise RuntimeError(f"F11 invariant violated: multiplier > 1.0 for {symbol}: {multiplier}")
        return max(0.0, min(1.0, multiplier))

    def on_bar(self, ctx) -> List[Dict]:
        """
        Generate daily orders: First construct features, then have LLM generate target positions, finally convert to buy/sell orders.
        ctx: {date, symbols, open_map/open_price_map, ref_price_map, portfolio, cfg, datasets, rejected_orders, ...}
        """
        # Call LLM to generate decisions
        open_map = ctx["open_map"]
        if not open_map:
            return []
        
        # 1) Feature construction
        features_list = self._build_features_for_day(ctx)
        features_list = self._attach_f11_pre_decision_context(features_list, ctx)
        
        # 2) Clean up expired historical records
        current_date = ctx["date"].strftime("%Y-%m-%d")
        self._cleanup_old_history(current_date)
        
        # 3) Build historical decision records for LLM call
        # Get current symbol list
        current_symbols = [fi["symbol"] for fi in features_list]
        
        # For backward compatibility, build previous_decisions format
        self.previous_decisions = self._build_previous_decisions_for_compatibility(current_date)
        
        # Get long-term historical records for prompt construction
        decision_history = self._get_decision_history_for_prompt(current_symbols)
        
        # Add detailed logs for historical records
        logger.debug(f"[DEBUG] LLM Strategy: current_date={current_date}")
        logger.debug(f"[DEBUG] LLM Strategy: long-term historical record statistics: total {len(self.decision_history)} symbols have historical records")
        for symbol, records in self.decision_history.items():
            if symbol in current_symbols:
                logger.debug(f"[DEBUG] LLM Strategy: {symbol} has {len(records)} historical records")
                if records:
                    latest_record = records[0]
                    logger.debug(f"[DEBUG] LLM Strategy: {symbol} latest record - date={latest_record['date']}, action={latest_record['decision'].get('action', 'unknown')}")
        
        # 4) Use unified executor for decision-making (automatically route to single or dual Agent mode based on configuration)
        logger.info(f"\n=== Unified Executor Decision Call Started ===")
        logger.info(f"[UNIFIED_EXECUTOR] Using unified executor for decision-making, Agent mode: {self.agent_mode}")
        logger.info(f"[UNIFIED_EXECUTOR] Agent mode in configuration: {(self.cfg or {}).get('agents', {}).get('mode', 'single')}")
        logger.info(f"[UNIFIED_EXECUTOR] Passed historical record parameters:")
        logger.debug(f"  - previous_decisions: {type(self.previous_decisions)} - {self.previous_decisions}")
        logger.debug(f"  - decision_history: {type(decision_history)} - {len(decision_history) if decision_history else 0} symbols")
        if decision_history:
            for symbol, records in decision_history.items():
                logger.debug(f"    {symbol}: {len(records)} records")
        
        # Build bars_data for feature conversion (complete version, including all data needed for dual-agent mode)
        bars_data = {}
        for fi in features_list:
            symbol = fi["symbol"]
            # Get historical data from ctx for feature conversion
            start_date = ctx["date"] - pd.Timedelta(days=self.warmup_days)  # Look back 60 days for feature construction
            end_date = ctx["date"]
            
            # Get market snapshot data
            ref_price = open_map.get(symbol, 0.0)
            snapshot = {
                "symbol": symbol,
                "price": ref_price,
                "ts_utc": ctx["date"].strftime("%Y-%m-%dT00:00:00Z")
            }
            
            # Get details data
            details = {"ticker": symbol}
            
            # Get news data (extract from original features to avoid duplicate API calls)
            news_items = []
            try:
                # Extract news data from already built features
                if "features" in fi and "news_events" in fi["features"]:
                    top_k_events = fi["features"]["news_events"].get("top_k_events", [])
                    # Convert news events to simple news_items format for decision agent
                    if isinstance(top_k_events, list) and top_k_events and top_k_events[0] != "No news data available":
                        for event in top_k_events:
                            if isinstance(event, str) and event.strip():
                                # Since top_k_events is already in title+description format from analysis,
                                # we can use it directly as title for the decision agent
                                news_items.append({
                                    "title": event,  # This already contains "title - description"
                                    "description": "",  # Keep empty since title already has full info
                                    "published_utc": ctx["date"].strftime("%Y-%m-%dT00:00:00Z")
                                })
            except Exception as e:
                logger.warning(f"Failed to extract news data from features {symbol}: {e}")
            
            # Get position state (extract from already built features)
            position_state = {}
            try:
                if "features" in fi and "position_state" in fi["features"]:
                    position_state = fi["features"]["position_state"].copy()
                else:
                    # Fallback plan: build default position state
                    position = ctx["portfolio"].positions.get(symbol)
                    current_position_value = 0.0
                    if position and hasattr(position, "shares") and position.shares:
                        from stockbench.core.price_utils import calculate_position_value
                        try:
                            current_position_value = calculate_position_value(
                                symbol=symbol,
                                shares=position.shares,
                                ctx=ctx,
                                portfolio=None,
                                position_avg_price=getattr(position, 'avg_price', None)
                            )
                        except Exception:
                            fallback_price = ref_price or 100.0
                            current_position_value = float(position.shares * fallback_price)
                    
                    holding_days = int(getattr(position, "holding_days", 0) or 0) if position else 0
                    position_state = {
                        "current_position_value": current_position_value,
                        "holding_days": holding_days,
                        "shares": round(float(getattr(position, "shares", 0) or 0), 2)
                    }
            except Exception as e:
                logger.warning(f"Failed to build position state {symbol}: {e}")
                position_state = {
                    "current_position_value": 0.0,
                    "holding_days": 0,
                    "shares": 0.0
                }
            
            bars_data[symbol] = {
                "bars_day": ctx["datasets"].get_day_bars(symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
                "snapshot": snapshot,
                "details": details,
                "news_items": news_items,
                "position_state": position_state
            }
        # Get run_id from ctx for organizing LLM cache directory
        run_id = ctx.get("run_id")
        
        # Extract rejected_orders from ctx for retry mechanism
        rejected_orders = ctx.get("rejected_orders", None)
        
        logger.info(f"[UNIFIED_EXECUTOR] Calling unified executor decision, automatically routing to correct Agent mode")
        logger.info(f"[UNIFIED_EXECUTOR] Parameter details:")
        logger.debug(f"  - features_list length: {len(features_list)}")
        logger.debug(f"  - cfg: {type(self.cfg)}")
        logger.debug(f"  - enable_llm: {True}")
        logger.debug(f"  - run_id: {run_id}")
        logger.debug(f"  - previous_decisions: {'Yes' if self.previous_decisions else 'No'}")
        logger.debug(f"  - decision_history: {'Yes' if decision_history else 'No'}")
        logger.debug(f"  - rejected_orders: {len(rejected_orders) if rejected_orders else 0} orders")
        
        if rejected_orders:
            logger.info(f"[UNIFIED_EXECUTOR] Processing {len(rejected_orders)} rejected orders for retry")
        
        decisions_map = unified_decide_batch(features_list, cfg=self.cfg, enable_llm=True, bars_data=bars_data, run_id=run_id, previous_decisions=self.previous_decisions, decision_history=decision_history, rejected_orders=rejected_orders, ctx=ctx)
        self._log_f11_dryruns(features_list, decisions_map, ctx)
        
        logger.info(f"[UNIFIED_EXECUTOR] Unified executor decision completed, return result type: {type(decisions_map)}")
        logger.info(f"[UNIFIED_EXECUTOR] Return result keys: {list(decisions_map.keys()) if decisions_map else 'None'}")
        logger.info(f"=== Unified Executor Decision Call Ended ===\n")
        
        # Note: Order rejection retry logic has been removed, unified retry mechanism will handle automatically

        # 4) Generate orders
        orders: List[Dict] = []
        pf = ctx["portfolio"]
        ref_price_map = ctx.get("ref_price_map", {}) or {}
        equity_for_sizing = float(ctx.get("equity_for_sizing") or 0.0)
        
        # Add debug logs
        logger.debug(f"[DEBUG] LLM Strategy: equity_for_sizing={equity_for_sizing}, portfolio.equity={pf.equity}")
        logger.debug(f"[DEBUG] LLM Strategy: feature_count={len(features_list)}, decision_count={len(decisions_map)}")
        
        for fi in features_list:
            s = fi["symbol"]
            decision = decisions_map.get(s, {})
            action = decision.get("action", "hold")
            
            ref_px =  open_map.get(s) # ref_price_map.get(s)
            
            if ref_px is None or ref_px <= 0:
                logger.debug(f"[DEBUG] LLM Strategy: {s} - skip, invalid reference price")
                continue
                
            pos = pf.positions.get(s)
            current_value = (pos.shares * float(ref_px)) if pos else 0.0
            
            # Fix target_cash_amount handling logic for hold operations
            if action == "hold" and "target_cash_amount" not in decision:
                # For hold operations without target_cash_amount, use current position value
                target_cash = current_value
                logger.debug(f"[DEBUG] LLM Strategy: {s} - hold operation auto-set target_cash={target_cash} (current position value)")
            else:
                target_cash = float(decision.get("target_cash_amount", 0.0))
            
            # Add debug information for each symbol
            logger.debug(f"[DEBUG] LLM Strategy: {s} - action={action}, target_cash={target_cash}, ref_px={ref_px}")
            # Directly use LLM output target cash amount, no need to convert to percentage
            target_value = max(0.0, target_cash)  # Ensure target amount is non-negative
            features = fi.get("features", {}) if isinstance(fi, dict) else {}
            f11_multiplier = self._f11_size_multiplier(
                s, action, current_value, target_value, decision, features, ctx, open_map
            )
            if abs(f11_multiplier - 1.0) > 1e-9:
                original_target_value = target_value
                target_value = current_value + (target_value - current_value) * f11_multiplier
                target_value = max(0.0, target_value)
                logger.info(
                    f"[F11_SIZE_ADJUST] {s}: action={action}, target_value "
                    f"{original_target_value:.2f} -> {target_value:.2f}, multiplier={f11_multiplier:.2f}"
                )
            delta_value = target_value - current_value
            
            logger.debug(f"[DEBUG] LLM Strategy: {s} - current_value={current_value}, target_value={target_value}, delta_value={delta_value}")
            
            # CRITICAL FIX: Detect and correct LLM decision logic errors
            # When target_cash_amount equals current_position_value, it should be a hold operation
            if action == "increase" and abs(delta_value) < 0.01:
                logger.warning(f"[DECISION_LOGIC_FIX] {s}: LLM marked as 'increase' but delta_value={delta_value:.4f} ≈ 0, treating as 'hold'")
                action = "hold"  # Override incorrect LLM decision
            elif action == "decrease" and abs(delta_value) < 0.01:
                logger.warning(f"[DECISION_LOGIC_FIX] {s}: LLM marked as 'decrease' but delta_value={delta_value:.4f} ≈ 0, treating as 'hold'")
                action = "hold"  # Override incorrect LLM decision
            
            # Only trigger trades under explicit actions
            if action == "increase" and delta_value > 0:
                qty = round(delta_value / float(ref_px), 2)
                if qty > 0:
                    orders.append({"symbol": s, "side": "buy", "qty": qty})
                    if self._f11_enabled("F11L_v2_SOFT_WEEKLY_BUY_ADD_THROTTLE"):
                        week_id = pd.Timestamp(current_date).strftime("%G-W%V")
                        self.f11_weekly_buy_add_counts[week_id] = self.f11_weekly_buy_add_counts.get(week_id, 0) + 1
                    logger.debug(f"[DEBUG] LLM Strategy: {s} - generated buy order: qty={qty}")
                else:
                    logger.debug(f"[DEBUG] LLM Strategy: {s} - skip, calculated quantity is 0")
            elif action in ("decrease", "close") and delta_value < 0:
                qty = round(abs(delta_value) / float(ref_px), 2)
                if pos and pos.shares > 0:
                    qty = min(qty, pos.shares)
                if qty > 0:
                    orders.append({"symbol": s, "side": "sell", "qty": -qty})
                    logger.debug(f"[DEBUG] LLM Strategy: {s} - generated sell order: qty={qty}")
                else:
                    logger.debug(f"[DEBUG] LLM Strategy: {s} - skip, calculated quantity is 0")
            else:
                logger.debug(f"[DEBUG] LLM Strategy: {s} - skip, action={action}, delta_value={delta_value}")
        
        logger.debug(f"[DEBUG] LLM Strategy: final generated order count={len(orders)}")
        
        # 5) Store pending decisions (to be recorded after execution)
        logger.info(f"\n=== Store Pending Decisions Started ===")
        logger.info(f"[PENDING_SAVE] Preparing to store pending decisions")
        logger.debug(f"[PENDING_SAVE] Current date: {current_date}")
        logger.debug(f"[PENDING_SAVE] Decision result type: {type(decisions_map)}")
        logger.debug(f"[PENDING_SAVE] Decision result keys: {list(decisions_map.keys()) if decisions_map else 'None'}")
        
        # Store pending decisions for later recording
        self.pending_decisions = decisions_map.copy() if decisions_map else {}
        
        # Store meta information
        meta = {"date": current_date, "calls": 1}
        if decisions_map and "__meta__" in decisions_map:
            decisions_map["__meta__"]["date"] = current_date
            meta.update(decisions_map["__meta__"])
            logger.debug(f"[PENDING_SAVE] Update meta info - date={current_date}")
            logger.debug(f"[PENDING_SAVE] Complete meta info: {meta}")
        else:
            logger.debug(f"[PENDING_SAVE] Using basic meta info: {meta}")
        
        self.pending_meta = meta.copy()
        
        # Print current decision result summary
        if decisions_map:
            logger.debug(f"\n[PENDING_SAVE] Current decision result summary:")
            for symbol, decision in decisions_map.items():
                if symbol != "__meta__":
                    action = decision.get("action", "unknown")
                    target_cash = decision.get("target_cash_amount", 0.0)
                    cash_change = decision.get("cash_change", 0.0)
                    confidence = decision.get("confidence", 0.0)
                    logger.debug(f"[PENDING_SAVE]   {symbol} - action={action}, target_cash_amount={target_cash}, cash_change={cash_change}, confidence={confidence}")
        
        logger.info(f"[PENDING_SAVE] Pending decisions stored, waiting for recording after trade execution")
        logger.info(f"=== Store Pending Decisions Completed ===\n")
        
        return orders 

    def record_executed_decisions(self, executed_symbols: List[str], portfolio=None) -> None:
        """Record decisions using intelligent recording strategy
        
        Strategy:
        1. Hold decisions: Record all (hold never gets rejected)
        2. Buy/sell decisions: Only record successfully executed ones
        
        Args:
            executed_symbols: List of symbols that were successfully executed
            portfolio: Portfolio object to get current shares information
        """
        if not self.pending_decisions:
            logger.debug(f"[DELAYED_RECORD] No pending decisions, skipping recording")
            return
            
        logger.info(f"\n=== Intelligent Decision Recording Started ===")
        logger.info(f"[SMART_RECORD] Implementing intelligent recording strategy:")
        logger.info(f"[SMART_RECORD] - Hold decisions: Record ALL (never get rejected)")
        logger.info(f"[SMART_RECORD] - Buy/sell decisions: Only record successfully executed ones")
        logger.info(f"[SMART_RECORD] Successfully executed symbols: {executed_symbols}")
        logger.info(f"[SMART_RECORD] Pending decision symbols: {list(self.pending_decisions.keys())}")
        
        # Use override mechanism: clear existing records for this date first to avoid duplicates
        current_date = self.pending_meta.get("date", "unknown")
        logger.info(f"[SMART_RECORD] Using override mechanism for date: {current_date}")
        
        # Intelligent recording strategy
        final_decisions = {}
        hold_count = 0
        executed_count = 0
        skipped_count = 0
        
        for symbol, decision in self.pending_decisions.items():
            if symbol.startswith("__"):  # Skip meta fields
                continue
                
            action = decision.get("action", "hold").lower()
            
            # Add current shares information from portfolio (after execution)
            if portfolio and hasattr(portfolio, 'positions'):
                position = portfolio.positions.get(symbol)
                if position and hasattr(position, 'shares'):
                    decision["shares"] = round(float(position.shares), 2)
                    logger.debug(f"[SMART_RECORD] {symbol}: Adding shares info: {decision['shares']}")
                else:
                    decision["shares"] = 0.0
                    logger.debug(f"[SMART_RECORD] {symbol}: No position, shares set to 0")
            else:
                logger.warning(f"[SMART_RECORD] {symbol}: No portfolio provided, cannot record shares")
                decision["shares"] = 0.0
            
            if action == "hold":
                # Strategy 1: Record all hold decisions (hold never gets rejected)
                final_decisions[symbol] = decision
                hold_count += 1
                logger.debug(f"[SMART_RECORD] {symbol}: HOLD decision recorded (hold decisions always recorded)")
            elif symbol in executed_symbols:
                # Strategy 2: Only record successfully executed buy/sell decisions
                final_decisions[symbol] = decision
                executed_count += 1
                logger.debug(f"[SMART_RECORD] {symbol}: {action.upper()} decision recorded (successfully executed)")
            else:
                # Buy/sell decision that was not executed (probably rejected) - skip recording
                skipped_count += 1
                logger.debug(f"[SMART_RECORD] {symbol}: {action.upper()} decision NOT recorded (not executed, likely rejected)")
        
        # Copy meta information
        if "__meta__" in self.pending_decisions:
            final_decisions["__meta__"] = self.pending_decisions["__meta__"]
        
        # Record final decisions with override mechanism
        if final_decisions:
            logger.info(f"\n[SMART_RECORD] Recording summary:")
            logger.info(f"  - Hold decisions recorded: {hold_count}")
            logger.info(f"  - Executed buy/sell decisions recorded: {executed_count}")
            logger.info(f"  - Rejected buy/sell decisions skipped: {skipped_count}")
            logger.info(f"  - Total decisions to record: {len([k for k in final_decisions.keys() if not k.startswith('__')])}")
            
            # Use override mechanism to ensure clean recording
            self._add_decision_to_history(
                current_date, 
                final_decisions, 
                self.pending_meta,
                clear_date_first=True  # Override mechanism: clear existing records for this date first
            )
        else:
            logger.debug(f"[SMART_RECORD] No decisions meet the recording criteria")
        
        # Clear pending decisions
        self.pending_decisions = {}
        self.pending_meta = {}
        logger.info(f"=== Intelligent Decision Recording Completed ===\n")
