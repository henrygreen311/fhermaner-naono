import time
import random
import threading
import sys
from mnemonic import Mnemonic
from web3 import Web3
import requests

# Force immediate output for CI environments
sys.stdout.reconfigure(line_buffering=True)

# Configuration
OUTPUT_FILE = "seed.txt"
API_FILE = "API.txt"
CHECK_INTERVAL = 1000  # Progress every 1000 attempts
REQUEST_INTERVAL = 1.0  # 1 request/second per API key
MAX_KEYS = 6  # Number of API keys to use

# Initialize BIP-39 mnemonic and Web3
mnemo = Mnemonic("english")
w3 = Web3()
w3.eth.account.enable_unaudited_hdwallet_features()

# Derivation paths for MetaMask and Trust Wallet
DERIVATION_PATHS = [
    "m/44'/60'/0'/0/0",  # MetaMask
    "m/44'/60'/0'/0/1"   # Trust Wallet
]

def read_api_keys():
    try:
        with open(API_FILE, "r") as f:
            keys = [line.strip() for line in f if line.strip()]
        if not keys:
            raise ValueError(f"{API_FILE} is empty")
        if len(keys) < MAX_KEYS:
            print(f"Warning: Only {len(keys)} API keys found, expected {MAX_KEYS}", flush=True)
        return keys[:MAX_KEYS]
    except FileNotFoundError:
        print(f"Error: {API_FILE} not found", flush=True)
        return None
    except Exception as e:
        print(f"Error reading {API_FILE}: {e}", flush=True)
        return None

def check_transactions(address, api_key, seed_phrase):
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=1&sort=asc&apikey={api_key}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "1":
                return len(data["result"])
            else:
                return 0
        else:
            return 0
    except Exception:
        return 0

def derive_address(seed_phrase, derivation_path):
    try:
        account = w3.eth.account.from_mnemonic(seed_phrase, account_path=derivation_path)
        return account.address
    except Exception:
        return None

def check_wallet_with_key(api_key, attempts_counter, lock):
    while True:
        seed_phrase = mnemo.generate(strength=128)
        found = False

        for path in DERIVATION_PATHS:
            address = derive_address(seed_phrase, path)
            if not address:
                continue

            transactions = check_transactions(address, api_key, seed_phrase)
            if transactions > 0:
                found = True
                print(f"Found wallet with {transactions} transactions", flush=True)
                print(f"Seed Phrase: {seed_phrase}", flush=True)
                print(f"Address: {address}", flush=True)
                entry = f"Seed Phrase: {seed_phrase}\nAddress: {address}\nPath: {path}\nTransactions: {transactions}\n"
                with open(OUTPUT_FILE, "a") as f:
                    f.write(entry + "\n")
                break  # Stop scanning other paths if one is successful

        with lock:
            attempts_counter[0] += 1
            if attempts_counter[0] % CHECK_INTERVAL == 0:
                elapsed = time.time() - attempts_counter[1]
                rate = attempts_counter[0] / elapsed if elapsed > 0 else 0
                print(f"Attempts {attempts_counter[0]}: {rate:.2f} wallets/sec", flush=True)

        time.sleep(REQUEST_INTERVAL)

def main():
    print("Generating random 12-word seed phrases for Ethereum wallets...", flush=True)
    print("Scanning 2 derivation paths (MetaMask and Trust Wallet) per seed phrase.", flush=True)
    print(f"Checking ~{MAX_KEYS} wallets/sec with {MAX_KEYS} API keys (1 request/sec/key).", flush=True)
    print(f"Appending wallets with transactions to {OUTPUT_FILE}.", flush=True)
    print("Note: This is not a recovery tool. Success rate is near-zero with random mnemonics.", flush=True)

    api_keys = read_api_keys()
    if not api_keys:
        print(f"Cannot proceed without valid API keys in {API_FILE}. Exiting.", flush=True)
        return

    attempts_counter = [0, time.time()]  # [attempts, start_time]
    lock = threading.Lock()

    threads = []
    for api_key in api_keys:
        t = threading.Thread(target=check_wallet_with_key, args=(api_key, attempts_counter, lock))
        t.daemon = True
        t.start()
        threads.append(t)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        elapsed = time.time() - attempts_counter[1]
        rate = attempts_counter[0] / elapsed if elapsed > 0 else 0
        print("Stopped", flush=True)
        print(f"Attempts {attempts_counter[0]}: {rate:.2f} wallets/sec in {elapsed:.1f} seconds", flush=True)
        print(f"Results saved to {OUTPUT_FILE}", flush=True)

if __name__ == "__main__":
    main()
