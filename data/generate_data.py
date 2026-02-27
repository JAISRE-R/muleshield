"""
MuleShield — Synthetic Transaction Dataset Generator
=====================================================
Generates realistic cross-channel banking transactions with labeled mule accounts.

Dataset Stats:
- 330 accounts (300 normal + 30 mules)
- 3 mule subtypes: complicit, recruited, exploited
- 7 payment channels
- 180-day window (Jan–Jun 2024)
- ~150K+ transactions
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

np.random.seed(42)
random.seed(42)

# ── Config ────────────────────────────────────────────────────────────────────
CHANNELS        = ["UPI", "NEFT", "IMPS", "ATM", "RTGS", "Mobile Banking", "Net Banking"]
START_DATE      = datetime(2024, 1, 1)
END_DATE        = datetime(2024, 6, 30)
TOTAL_DAYS      = (END_DATE - START_DATE).days

N_NORMAL        = 300
N_MULE          = 30   # 10 per subtype
N_EXTERNAL      = 50   # external entities (criminals, victims) — not account holders

NORMAL_IDS      = [f"ACC{str(i).zfill(5)}" for i in range(1, N_NORMAL + 1)]
MULE_IDS        = [f"MUL{str(i).zfill(5)}" for i in range(1, N_MULE + 1)]
EXTERNAL_IDS    = [f"EXT{str(i).zfill(5)}" for i in range(1, N_EXTERNAL + 1)]
ALL_ACCOUNT_IDS = NORMAL_IDS + MULE_IDS

# Mule subtypes
COMPLICIT_MULES = MULE_IDS[0:10]    # knowingly laundering
RECRUITED_MULES = MULE_IDS[10:20]   # tricked into it
EXPLOITED_MULES = MULE_IDS[20:30]   # account taken over

def rand_ts(start_day=0, end_day=None, night_bias=False):
    """Generate a random timestamp within the window."""
    if end_day is None:
        end_day = TOTAL_DAYS
    day = random.randint(start_day, end_day)
    if night_bias:
        # 70% chance of night hours (11pm–4am)
        if random.random() < 0.70:
            hour = random.choice(list(range(23, 24)) + list(range(0, 5)))
        else:
            hour = random.randint(8, 22)
    else:
        hour = random.randint(8, 22)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return START_DATE + timedelta(days=day, hours=hour, minutes=minute, seconds=second)

def round_amount(amount):
    """Occasionally round to nearest 1000 (smurfing signal)."""
    if random.random() < 0.25:
        return round(amount / 1000) * 1000
    return round(amount, 2)

transactions = []
txn_counter  = 1

def add_txn(account_id, txn_type, amount, channel, counterparty, ts, is_mule, mule_type="none"):
    global txn_counter
    transactions.append({
        "txn_id":       f"TXN{str(txn_counter).zfill(8)}",
        "timestamp":    ts.strftime("%Y-%m-%d %H:%M:%S"),
        "account_id":   account_id,
        "txn_type":     txn_type,          # credit / debit
        "amount":       amount,
        "channel":      channel,
        "counterparty": counterparty,
        "is_mule":      is_mule,           # 0 or 1
        "mule_type":    mule_type,         # none / complicit / recruited / exploited
    })
    txn_counter += 1

# ── Normal Accounts ───────────────────────────────────────────────────────────
print("Generating normal account transactions...")
for acc in NORMAL_IDS:
    n_txns = random.randint(200, 600)
    for _ in range(n_txns):
        ts          = rand_ts()
        txn_type    = random.choice(["credit", "debit"])
        counterparty= random.choice([a for a in ALL_ACCOUNT_IDS if a != acc])
        amount      = round(np.random.lognormal(9.5, 1.0), 2)   # ~₹5K–₹2L
        channel     = random.choice(CHANNELS)
        add_txn(acc, txn_type, amount, channel, counterparty, ts, is_mule=0)

# ── Complicit Mules ───────────────────────────────────────────────────────────
# Pattern: new account, many senders → rapid forward to 1-2 criminal receivers
# Night-hour heavy, round amounts, rapid channel switching
print("Generating complicit mule transactions...")
for acc in COMPLICIT_MULES:
    criminal_receivers = random.sample(EXTERNAL_IDS[:20], k=random.randint(1, 2))
    victim_senders     = random.sample(NORMAL_IDS, k=random.randint(8, 20))
    # Account opened recently — transactions only in last 60 days
    start_day = TOTAL_DAYS - 60

    for sender in victim_senders:
        # Receive from multiple victims
        n_credits = random.randint(3, 8)
        for _ in range(n_credits):
            ts     = rand_ts(start_day=start_day, night_bias=True)
            amount = round_amount(random.uniform(20000, 200000))
            add_txn(acc, "credit", amount, random.choice(["UPI", "NEFT", "IMPS"]),
                    sender, ts, is_mule=1, mule_type="complicit")

        # Forward almost immediately to criminal (within hours, different channel)
        for _ in range(n_credits):
            ts_forward = rand_ts(start_day=start_day, night_bias=True)
            amount_out = round_amount(amount * random.uniform(0.92, 0.99))  # slight skim
            receiver   = random.choice(criminal_receivers)
            out_channel= random.choice(["NEFT", "RTGS", "Net Banking"])
            add_txn(acc, "debit", amount_out, out_channel,
                    receiver, ts_forward, is_mule=1, mule_type="complicit")

# ── Recruited Mules ───────────────────────────────────────────────────────────
# Pattern: existing account, sudden behavioral shift after ~day 60
# Volume increases sharply, new counterparties appear
print("Generating recruited mule transactions...")
for acc in RECRUITED_MULES:
    criminal_handlers = random.sample(EXTERNAL_IDS[20:35], k=random.randint(1, 3))

    # Phase 1: Normal behavior (first 60 days)
    for _ in range(random.randint(50, 120)):
        ts           = rand_ts(start_day=0, end_day=60)
        txn_type     = random.choice(["credit", "debit"])
        counterparty = random.choice(NORMAL_IDS)
        amount       = round(np.random.lognormal(9.0, 0.8), 2)
        add_txn(acc, txn_type, amount, random.choice(CHANNELS),
                counterparty, ts, is_mule=0, mule_type="recruited")

    # Phase 2: Mule behavior (after day 60 — sudden shift)
    for _ in range(random.randint(80, 200)):
        ts     = rand_ts(start_day=61, night_bias=True)
        amount = round_amount(random.uniform(15000, 150000))

        if random.random() < 0.55:
            # Receive from handler
            sender = random.choice(criminal_handlers)
            add_txn(acc, "credit", amount, random.choice(["UPI", "IMPS"]),
                    sender, ts, is_mule=1, mule_type="recruited")
        else:
            # Forward to another mule or external
            receiver = random.choice(MULE_IDS + EXTERNAL_IDS[:15])
            add_txn(acc, "debit", amount * random.uniform(0.88, 0.98),
                    random.choice(["NEFT", "ATM", "Net Banking"]),
                    receiver, ts, is_mule=1, mule_type="recruited")

# ── Exploited Mules ───────────────────────────────────────────────────────────
# Pattern: account takeover — normal history, then sudden foreign IP behaviour
# Rapid large debits, new devices, unusual channels for this account
print("Generating exploited mule transactions...")
for acc in EXPLOITED_MULES:
    attacker_destinations = random.sample(EXTERNAL_IDS[35:], k=random.randint(2, 4))

    # Phase 1: Legitimate account history
    for _ in range(random.randint(100, 250)):
        ts           = rand_ts(start_day=0, end_day=90)
        txn_type     = random.choice(["credit", "debit"])
        counterparty = random.choice(NORMAL_IDS)
        amount       = round(np.random.lognormal(8.5, 0.7), 2)
        channel      = random.choice(["UPI", "Mobile Banking"])  # consistent channel
        add_txn(acc, txn_type, amount, channel,
                counterparty, ts, is_mule=0, mule_type="exploited")

    # Phase 2: Post-takeover — large rapid debits via unusual channels
    takeover_day = random.randint(91, 120)
    for _ in range(random.randint(10, 30)):
        ts     = rand_ts(start_day=takeover_day, end_day=takeover_day + 3, night_bias=True)
        amount = round_amount(random.uniform(50000, 500000))  # much larger than normal
        dest   = random.choice(attacker_destinations)
        channel= random.choice(["RTGS", "Net Banking", "NEFT"])  # different from normal
        add_txn(acc, "debit", amount, channel,
                dest, ts, is_mule=1, mule_type="exploited")

# ── Save ──────────────────────────────────────────────────────────────────────
df = pd.DataFrame(transactions)
df = df.sort_values("timestamp").reset_index(drop=True)

output_path = "transactions.csv"
df.to_csv(output_path, index=False)

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*50)
print("DATASET GENERATED SUCCESSFULLY")
print("="*50)
print(f"Total transactions : {len(df):,}")
print(f"Total accounts     : {df['account_id'].nunique()}")
print(f"Mule transactions  : {df['is_mule'].sum():,} ({df['is_mule'].mean()*100:.1f}%)")
print(f"Date range         : {df['timestamp'].min()} → {df['timestamp'].max()}")
print(f"Channels           : {sorted(df['channel'].unique())}")
print(f"\nMule type breakdown:")
print(df[df['is_mule']==1]['mule_type'].value_counts().to_string())
print(f"\nSaved to: {output_path}")
print("="*50)
