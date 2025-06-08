import time
import random
import concurrent.futures
from mnemonic import Mnemonic
from web3 import Web3
import requests

# Configuration
OUTPUT_FILE = "seed.txt"
API_FILE = "API.txt"
CHECK_INTERVAL = 500  # Progress every 500 attempts
CHECK_TOKENS = True
TOKEN_CONTRACTS = [
    ("0xdAC17F958D2ee523a2206206994597C13D831ec7", "USDT", 6),  # USDT
    ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC", 6)   # USDC
]
MAX_WORKERS = 6  # Threads for ~5-10 wallets/sec
BATCH_SIZE = 12  # Wallets per batch
REQUEST_DELAY = 0.1  # Delay per thread to avoid rate limits

# Initialize BIP-39 mnemonic and Web3
mnemo = Mnemonic("english")
w3 = Web3()
w3.eth.account.enable_unaudited_hdwallet_features()

def read_api_keys():
    # Read Etherscan API keys from file
    try:
        with open(API_FILE, "r") as f:
            keys = [line.strip() for line in f if line.strip()]
        if not keys:
            raise ValueError(f"{API_FILE} is empty")
        return keys
    except FileNotFoundError:
        print(f"Error: {API_FILE} not found")
        return None
    except Exception as e:
        print(f"Error reading {API_FILE}: {e}")
        return None

def check_eth_balance(address, api_key, seed_phrase):
    # Check ETH balance
    url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "1":
                return int(data["result"]) / 10**18
            else:
                print(f"ETH balance check failed for {address} (Seed: {seed_phrase}): {data['message']}")
                return 0
        else:
            print(f"ETH balance check HTTP error for {address} (Seed: {seed_phrase}): {response.status_code}")
            return 0
    except Exception as e:
        print(f"ETH balance check error for {address} (Seed: {seed_phrase}): {e}")
        return 0

def check_token_balance(address, contract_address, token_name, decimals, api_key, seed_phrase):
    # Check ERC-20 token balance
    url = f"https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={address}&tag=latest&apikey={api_key}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "1":
                return int(data["result"]) / 10**decimals
            else:
                print(f"{token_name} balance check failed for {address} (Seed: {seed_phrase}): {data['message']}")
                return 0
        else:
            print(f"{token_name} balance check HTTP error for {address} (Seed: {seed_phrase}): {response.status_code}")
            return 0
    except Exception as e:
        print(f"{token_name} balance check error for {address} (Seed: {seed_phrase}): {e}")
        return 0

def derive_address(seed_phrase):
    # Derive Ethereum address from seed phrase
    try:
        account = w3.eth.account.from_mnemonic(seed_phrase)
        return account.address
    except Exception:
        return None

def check_wallet(seed_phrase, api_keys):
    # Check wallet for funds
    address = derive_address(seed_phrase)
    if not address:
        return None

    api_key = random.choice(api_keys)
    eth_balance = check_eth_balance(address, api_key, seed_phrase)
    token_balances = []
    if CHECK_TOKENS:
        for contract, token_name, decimals in TOKEN_CONTRACTS:
            balance = check_token_balance(address, contract, token_name, decimals, api_key, seed_phrase)
            if balance > 0:
                token_balances.append((token_name, balance))
            time.sleep(REQUEST_DELAY)  # Delay per token request

    if eth_balance > 0 or token_balances:
        entry = f"Seed Phrase: {seed_phrase}\nAddress: {address}\nETH Balance: {eth_balance} ETH\n"
        if token_balances:
            entry += "Token Balances:\n" + "\n".join(f"  {name}: {bal}" for name, bal in token_balances) + "\n"
        return entry
    return None

def main():
    print("Generating random 12-word seed phrases for MetaMask (Ethereum) wallets...")
    print(f"Checking ~5-10 wallets/sec in parallel with {MAX_WORKERS} threads.")
    print(f"Appending wallets with ETH or ERC-20 funds to {OUTPUT_FILE}.")
    print("Logging failed API checks and funded wallets to console.")
    print("Note: Without a target address or partial seed, this is unlikely to recover your wallet.")

    # Read API keys
    api_keys = read_api_keys()
    if not api_keys:
        print(f"Cannot proceed without valid API keys in {API_FILE}. Exiting.")
        return

    attempts = 0
    start_time = time.time()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            while True:
                # Generate batch of seed phrases
                seed_phrases = [mnemo.generate(strength=128) for _ in range(BATCH_SIZE)]
                attempts += BATCH_SIZE

                # Submit tasks in parallel
                futures = [executor.submit(check_wallet, sp, api_keys) for sp in seed_phrases]
                for future in concurrent.futures.as_completed(futures):
                    entry = future.result()
                    if entry:
                        print("Found wallet with funds")
                        print(entry.strip())
                        with open(OUTPUT_FILE, "a") as f:
                            f.write(entry + "\n")

                # Progress update
                if attempts % CHECK_INTERVAL == 0:
                    elapsed = time.time() - start_time
                    rate = attempts / elapsed if elapsed > 0 else 0
                    print(f"Generated {attempts} seed phrases... ({rate:.2f} phrases/second)")

                time.sleep(REQUEST_DELAY)  # Delay per batch

    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        rate = attempts / elapsed if elapsed > 0 else 0
        print("\nStopped by user.")
        print(f"Generated {attempts} seed phrases in {elapsed:.2f} seconds ({rate:.2f} phrases/second).")
        print(f"Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
