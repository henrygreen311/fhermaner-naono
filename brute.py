import time
import random
import threading
from mnemonic import Mnemonic
from web3 import Web3
import requests

# Configuration
OUTPUT_FILE = "seed.txt"
API_FILE = "API.txt"
CHECK_INTERVAL = 500  # Progress every 500 attempts
REQUEST_INTERVAL = 1.0  # 1 request/second per API key
MAX_KEYS = 6  # Number of API keys to use

# Derivation paths to scan (MetaMask and Trust Wallet)
DERIVATION_PATHS = [
    "m/44'/60'/0'/0/0",  # MetaMask standard path
    "m/44'/60'/0'/0/1"   # Trust Wallet common alternate path
]

# Initialize BIP-39 mnemonic and Web3
mnemo = Mnemonic("english")
w3 = Web3()
w3.eth.account.enable_unaudited_hdwallet_features()

def read_api_keys():
    try:
        with open(API_FILE, "r") as f:
            keys = [line.strip() for line in f if line.strip()]
        if not keys:
            raise ValueError(f"{API_FILE} is empty")
        if len(keys) < MAX_KEYS:
            print(f"Warning: Only {len(keys)} API keys found, expected {MAX_KEYS}")
        return keys[:MAX_KEYS]
    except FileNotFoundError:
        print(f"Error: {API_FILE} not found")
        return None
    except Exception as e:
        print(f"Error reading {API_FILE}: {e}")
        return None

def check_transactions(address, api_key):
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset=1&sort=asc&apikey={api_key}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "1":
                return len(data["result"])
            else:
                return 0  # Do not log "No transactions found" to console
        else:
            return 0
    except Exception:
        return 0

def derive_addresses(seed_phrase):
    addresses = []
    for path in DERIVATION_PATHS:
        try:
            account = w3.eth.account.from_mnemonic(seed_phrase, account_path=path)
            addresses.append(account.address)
        except Exception:
            continue
    return addresses

def check_wallet_with_key(api_key, attempts_counter, lock):
    while True:
        seed_phrase = mnemo.generate(strength=128)
        addresses = derive_addresses(seed_phrase)

        for address in addresses:
            transactions = check_transactions(address, api_key)
            if transactions > 0:
                entry = f"Seed Phrase: {seed_phrase}\nAddress: {address}\nTransactions: {transactions}\n"
                with open(OUTPUT_FILE, "a") as f:
                    f.write(entry + "\n")
                print("Found wallet with transactions:")
                print(entry.strip())
                break  # Stop scanning other paths for this seed

        with lock:
            attempts_counter[0] += 1
            if attempts_counter[0] % CHECK_INTERVAL == 0:
                elapsed = time.time() - attempts_counter[1]
                rate = attempts_counter[0] / elapsed if elapsed > 0 else 0
                print(f"Attempts {attempts_counter[0]}: {rate:.2f} wallets/sec")

        time.sleep(REQUEST_INTERVAL)

def main():
    print("Generating random 12-word seed phrases for Ethereum wallets...")
    print("Scanning 2 derivation paths (MetaMask and Trust Wallet) per seed phrase.")
    print(f"Checking ~{MAX_KEYS} wallets/sec with {MAX_KEYS} API keys (1 request/sec/key).")
    print(f"Appending wallets with transactions to {OUTPUT_FILE}.")
    print("Note: This is not a recovery tool. Success rate is near-zero with random mnemonics.")

    api_keys = read_api_keys()
    if not api_keys:
        print(f"Cannot proceed without valid API keys in {API_FILE}. Exiting.")
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
        print("\nStopped")
        print(f"Attempts {attempts_counter[0]}: {rate:.2f} wallets/sec in {elapsed:.1f} seconds")
        print(f"Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
