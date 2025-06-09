import time
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

# Initialize BIP-39 mnemonic and Web3
mnemo = Mnemonic("english")
w3 = Web3()
w3.eth.account.enable_unaudited_hdwallet_features()

# Derivation path (MetaMask default)
ETH_DERIVATION_PATH = "m/44'/60'/0'/0/0"

def read_api_keys():
    try:
        with open(API_FILE, "r") as f:
            keys = [line.strip() for line in f if line.strip()]
        if not keys:
            print(f"No API keys found in {API_FILE}.", flush=True)
        return keys
    except Exception as e:
        print(f"Error reading API keys: {e}", flush=True)
        return None

def derive_eth_address(seed_phrase):
    try:
        account = w3.eth.account.from_mnemonic(seed_phrase, account_path=ETH_DERIVATION_PATH)
        return account.address
    except Exception:
        return None

def check_erc20_transactions(address, api_key):
    url = f"https://api.etherscan.io/api?module=account&action=tokentx&address={address}&page=1&offset=10&sort=asc&apikey={api_key}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data["status"] == "1" and data["result"]:
                return len(data["result"])
    except Exception:
        pass
    return 0

def check_wallet(api_key, attempts_counter, lock):
    while True:
        seed_phrase = mnemo.generate(strength=128)
        eth_address = derive_eth_address(seed_phrase)

        token_tx_count = check_erc20_transactions(eth_address, api_key) if eth_address else 0

        if token_tx_count > 0:
            print(f"Found wallet with ERC-20 token activity:", flush=True)
            print(f"Seed Phrase: {seed_phrase}", flush=True)
            print(f"ETH Address: {eth_address}", flush=True)
            print(f"ERC-20 Tx Count: {token_tx_count}", flush=True)
            entry = (
                f"Seed Phrase: {seed_phrase}\n"
                f"ETH Address: {eth_address}\n"
                f"ERC-20 Tx Count: {token_tx_count}\n\n"
            )
            with open(OUTPUT_FILE, "a") as f:
                f.write(entry)

        with lock:
            attempts_counter[0] += 1
            if attempts_counter[0] % CHECK_INTERVAL == 0:
                elapsed = time.time() - attempts_counter[1]
                rate = attempts_counter[0] / elapsed if elapsed > 0 else 0
                print(f"Attempts {attempts_counter[0]}: {rate:.2f} wallets/sec", flush=True)

        time.sleep(REQUEST_INTERVAL)

def main():
    print("Generating random 12-word seed phrases for Ethereum wallets (MetaMask path)...", flush=True)
    print("Checking only ERC-20 token transactions per wallet (includes ETH transfers).", flush=True)
    print(f"Using Etherscan API keys from {API_FILE}.", flush=True)
    print(f"Appending wallets with token activity to {OUTPUT_FILE}.", flush=True)
    print("Note: God will surely do his wILL, AMEN", flush=True)

    api_keys = read_api_keys()
    if not api_keys:
        print(f"Need at least 1 API key in {API_FILE}. Exiting.", flush=True)
        return

    attempts_counter = [0, time.time()]  # [count, start_time]
    lock = threading.Lock()

    threads = []
    for api_key in api_keys:
        t = threading.Thread(target=check_wallet, args=(api_key, attempts_counter, lock))
        t.daemon = True
        t.start()
        threads.append(t)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        elapsed = time.time() - attempts_counter[1]
        rate = attempts_counter[0] / elapsed if elapsed > 0 else 0
        print("\nStopped", flush=True)
        print(f"Attempts {attempts_counter[0]}: {rate:.2f} wallets/sec in {elapsed:.1f} seconds", flush=True)
        print(f"Results saved to {OUTPUT_FILE}", flush=True)

if __name__ == "__main__":
    main()
