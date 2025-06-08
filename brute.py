import time
import random
from mnemonic import Mnemonic
from web3 import Web3
import requests

# Configuration
OUTPUT_FILE = "seed.txt"
API_FILE = "API.txt"
CHECK_INTERVAL = 1000  # Print progress every 1,000 attempts
REQUEST_DELAY = 0.2  # Seconds between API requests (adjust for rate limits)
CHECK_TOKENS = True  # Check ERC-20 token balances
TOKEN_CONTRACTS = [
    ("0xdAC17F958D2ee523a2206206994597C13D831ec7", "USDT", 6),  # USDT (6 decimals)
    ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", "USDC", 6),  # USDC (6 decimals)
    # Add more: (contract_address, token_name, decimals)
]

# Initialize BIP-39 mnemonic and Web3
mnemo = Mnemonic("english")
w3 = Web3()

# Enable unaudited HD wallet features
w3.eth.account.enable_unaudited_hdwallet_features()

def read_api_keys():
    """
    Read Etherscan API keys from API.txt.
    """
    try:
        with open(API_FILE, "r") as f:
            keys = [line.strip() for line in f if line.strip()]
        if not keys:
            raise ValueError(f"{API_FILE} is empty")
        return keys
    except FileNotFoundError:
        print(f"Error: {API_FILE} not found")
        return []
    except Exception as e:
        print(f"Error reading {API_FILE}: {e}")
        return []

def check_eth_balance(address, api_key):
    """
    Check ETH balance using Etherscan API.
    """
    url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "1":
                return int(data["result"]) / 10**18  # Convert wei to ETH
            return 0
        return 0
    except Exception:
        return 0

def check_token_balance(address, contract_address, token_name, decimals, api_key):
    """
    Check ERC-20 token balance using Etherscan API.
    """
    url = f"https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={address}&tag=latest&apikey={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data["status"] == "1":
                return int(data["result"]) / 10**decimals  # Adjust for token decimals
            return 0
        return 0
    except Exception:
        return 0

def derive_address(seed_phrase):
    """
    Derive Ethereum address from a seed phrase.
    """
    try:
        account = w3.eth.account.from_mnemonic(seed_phrase)
        return account.address
    except Exception:
        return None

def main():
    print("Generating random 12-word seed phrases for MetaMask (Ethereum) wallets...")
    print("Running indefinitely until manually stopped (Ctrl+C).")
    print(f"Appending wallets with ETH or ERC-20 funds to {OUTPUT_FILE}.")
    print("Minimal logging enabled to avoid system overload.")
    print("Note: Without a target address or partial seed, this is unlikely to recover your wallet.")

    # Read API keys
    api_keys = read_api_keys()
    if not api_keys:
        print(f"Cannot proceed without valid API keys in {API_FILE}. Exiting.")
        return

    attempts = 0
    start_time = time.time()
    try:
        while True:
            # Generate a random 12-word seed phrase
            seed_phrase = mnemo.generate(strength=128)
            attempts += 1

            # Derive Ethereum address
            address = derive_address(seed_phrase)
            if not address:
                continue

            # Select random API key
            api_key = random.choice(api_keys)

            # Check balances
            eth_balance = check_eth_balance(address, api_key)
            token_balances = []
            if CHECK_TOKENS:
                for contract, token_name, decimals in TOKEN_CONTRACTS:
                    balance = check_token_balance(address, contract, token_name, decimals, api_key)
                    if balance > 0:
                        token_balances.append((token_name, balance))

            # Save if funds found
            if eth_balance > 0 or token_balances:
                entry = f"Seed Phrase: {seed_phrase}\nAddress: {address}\nETH Balance: {eth_balance} ETH\n"
                if token_balances:
                    entry += "Token Balances:\n" + "\n".join(f"  {name}: {bal}" for name, bal in token_balances) + "\n"
                print(f"!!! Found wallet with funds !!!")
                print(entry.strip())
                with open(OUTPUT_FILE, "a") as f:
                    f.write(entry + "\n")
            
            # Progress update
            if attempts % CHECK_INTERVAL == 0:
                elapsed = time.time() - start_time
                rate = attempts / elapsed if elapsed > 0 else 0
                print(f"Generated {attempts} seed phrases... ({rate:.2f} phrases/second)")

            # Delay to respect Etherscan rate limits
            time.sleep(REQUEST_DELAY)

    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        rate = attempts / elapsed if elapsed > 0 else 0
        print(f"\nStopped by user.")
        print(f"Generated {attempts} seed phrases in {elapsed:.2f} seconds ({rate:.2f} phrases/second).")
        print(f"Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
