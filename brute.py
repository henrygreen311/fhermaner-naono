import time
import threading
import sys
from mnemonic import Mnemonic
from web3 import Web3
import requests
from tronpy import Tron
from tronpy.keys import PrivateKey

# Force stdout flush for CI environments
sys.stdout.reconfigure(line_buffering=True)

# Config
OUTPUT_FILE = "seed.txt"
API_FILE = "API.txt"
TRON_API_FILE = "TRON.txt"
CHECK_INTERVAL = 1000
REQUEST_INTERVAL = 1.0  # One request per second per API

# Initialize tools
mnemo = Mnemonic("english")
w3 = Web3()
w3.eth.account.enable_unaudited_hdwallet_features()

# Derivation path for Ethereum (MetaMask)
ETH_DERIVATION_PATH = "m/44'/60'/0'/0/0"
# Standard Trust Wallet path for TRON (still used for address derivation)
TRON_DERIVATION_PATH = "m/44'/195'/0'/0/0"

def read_api_keys(path):
    try:
        with open(path, "r") as f:
            keys = [line.strip() for line in f if line.strip()]
        return keys if keys else None
    except Exception as e:
        print(f"Error reading {path}: {e}", flush=True)
        return None

def derive_eth_address(seed_phrase):
    try:
        account = w3.eth.account.from_mnemonic(seed_phrase, account_path=ETH_DERIVATION_PATH)
        return account.address
    except Exception:
        return None

def derive_tron_address(seed_phrase):
    try:
        priv = w3.eth.account.from_mnemonic(seed_phrase, account_path=TRON_DERIVATION_PATH).key
        private_key = PrivateKey(bytes.fromhex(priv.hex()))
        return private_key.public_key.to_base58check_address()
    except Exception:
        return None

def check_erc20_tokentx(address, api_key):
    url = (
        f"https://api.etherscan.io/api"
        f"?module=account&action=tokentx&address={address}&page=1&offset=10&sort=asc&apikey={api_key}"
    )
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if r.status_code == 200 and data["status"] == "1" and data["result"]:
            return len(data["result"])
    except Exception:
        pass
    return 0

def check_trc20_tokentx(address, api_key):
    url = f"https://apilist.tronscanapi.com/api/token_trc20/transfers?limit=1&start=0&sort=-timestamp&count=true&toAddress={address}&fromAddress={address}"
    headers = {
        "TRON-PRO-API-KEY": api_key  # optional for Tronscan; include if required
    }
    try:
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        if r.status_code == 200 and "data" in data and data["data"]:
            return len(data["data"])
    except Exception:
        pass
    return 0

def check_wallets(eth_api_key, tron_api_key, attempts_counter, lock):
    while True:
        seed = mnemo.generate(strength=128)
        eth_address = derive_eth_address(seed)
        tron_address = derive_tron_address(seed)

        eth_hits = check_erc20_tokentx(eth_address, eth_api_key) if eth_address else 0
        tron_hits = check_trc20_tokentx(tron_address, tron_api_key) if tron_address else 0

        if eth_hits > 0 or tron_hits > 0:
            print(f"Found wallet with token activity:", flush=True)
            print(f"Seed Phrase: {seed}", flush=True)
            if eth_hits > 0:
                print(f"ETH Address: {eth_address} | ERC-20 TokenTxs: {eth_hits}", flush=True)
            if tron_hits > 0:
                print(f"TRON Address: {tron_address} | TRC-20 TokenTxs: {tron_hits}", flush=True)

            with open(OUTPUT_FILE, "a") as f:
                f.write(f"Seed Phrase: {seed}\n")
                if eth_hits > 0:
                    f.write(f"ETH Address: {eth_address}\nERC-20 TokenTx Count: {eth_hits}\n")
                if tron_hits > 0:
                    f.write(f"TRON Address: {tron_address}\nTRC-20 TokenTx Count: {tron_hits}\n")
                f.write("\n")

        with lock:
            attempts_counter[0] += 1
            if attempts_counter[0] % CHECK_INTERVAL == 0:
                elapsed = time.time() - attempts_counter[1]
                rate = attempts_counter[0] / elapsed if elapsed > 0 else 0
                print(f"Attempts: {attempts_counter[0]} | Rate: {rate:.2f} wallets/sec", flush=True)

        time.sleep(REQUEST_INTERVAL)

def main():
    print("Generating random 12-word seed phrases for Ethereum and TRON wallets...", flush=True)
    print("Checking for ERC-20 and TRC-20 token transfer activity...", flush=True)
    print(f"Using Etherscan API keys from {API_FILE}", flush=True)
    print(f"Using Tronscan API keys from {TRON_API_FILE}", flush=True)
    print(f"Logging results to {OUTPUT_FILE}", flush=True)

    eth_api_keys = read_api_keys(API_FILE)
    tron_api_keys = read_api_keys(TRON_API_FILE)

    if not eth_api_keys or not tron_api_keys:
        print("Missing API keys in API.txt or TRON.txt. Exiting.", flush=True)
        return

    if len(eth_api_keys) != 12 or len(tron_api_keys) != 12:
        print("Expected 12 API keys in each file. Exiting.", flush=True)
        return

    attempts_counter = [0, time.time()]
    lock = threading.Lock()

    threads = []
    for i in range(12):
        for _ in range(3):  # 3 threads per key
            t = threading.Thread(
                target=check_wallets,
                args=(eth_api_keys[i], tron_api_keys[i], attempts_counter, lock),
            )
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
        print(f"Attempts: {attempts_counter[0]} | Rate: {rate:.2f} wallets/sec | Time: {elapsed:.1f} seconds")
        print(f"Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
