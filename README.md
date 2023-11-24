# Hack Peanut ECO deposits

This repo contains `hack.py` file that demonstrates how ECO tokens can be stolen from Peanut.

The script demonstrates how to steal ECO from Peanut V3 on Optimism since this contract holds the most ECO tokens, but in general all Peanut contracts (V3, V4, V5) across all chains where ECO is deployed are at risk.

## Impact of the bug

All ECO tokens across all Peanut contracts can be stolen.

## What is the vulnerability?

In Peanut contracts, there is dedicated support for ECO token (which is inflationary). In case of Peanut V3, there are special `contractType` 4 and 5 that are used for ECO deposits. However, Peanut doesn't restrict the users from depositing ECO with `contractType = 1` (i.e. as a casual ERC20 token).

ECO token is inflationary. Let's call ECO's inflation multiplier as `mult`. So, ECO transfers work as follows:

1. User calls ECO.transfer(recipient, amount)
2. ECO contract under the hood transfers `amount * mult`.

`mult` is something that slowely increases over time. At the time of writing it is `~1.025` on Optimism (i.e. the inflation is 2.5%).

So let's say a user calls Peanut's makeDeposit function with `X` being the amount of ECO tokens that they wish to deposit. The amount transferred under the hood is `X * mult1` (let's call current multiplier value `mult1`).

Now, let's say that an inflation event has occured and mult is now `1.035` (i.e. the inflation is 3.5%). The user withdraws their deposit. The Peanut contract calls ECO.transfer(`X`). Everything seems smooth, but! Under the hood ECO contract transfers `X * mult2` ECO tokens from Peanut to the user.

Since mult2 is greater than mult1, the user recevies `X * (mult2 - mult1)` more ECO tokens that hey initially deposited. And this extra is taken from the general Peanut ECO balance, i.e. from other Peanut deposits.

So, if during ECO's inflation increase event, sombody:

1. Deposits ECO tokens to Peanut via `contractType = 1` (i.e. pure ERC20 token deposit)
2. Waits until the inflation multiplier is increased
3. Withdraws the deposited tokens

They receive more tokens than they deposited. And thus are able to steal all ECO tokens in a certain Peanut contract.

## How to reproduce?

The python script that I made works with a Tenderly DevNet fork of Optimism Mainnet. So, in order to reproduce the attack, do the following:

1. Create a Tenderl DevNet
   1. Go to https://tenderly.co/devnets
   2. Create a tenderly account if you don't have one yet
   3. Click "Create Template" button in top right
   4. In the YAML template field paste the content from `tenderly-config.yaml` in this repo.
   5. Click "Create". This will create a pure fork of current state of Optimism Mainnet with no modifications.
   6. Click on the created template.
   7. Click "Spawn DevNet" button.
   8. Copy the rpc url and insert it in `OPTIMISM_RPC` constant at the top of `hack.py` file.
2. Setup python environment
   1. Create a python virtual environment. I personally used python3.11 and created the venv via `python3.11 -m venv venv`, but the script might work with other python versions too (I have not tested though).
   2. Activate the venv via `source venv/bin/activate`
   3. Install packages via `pip install -r requirements.txt`
3. Hack it! Type `python hack.py`.

The script will airdrop some ETH and some ECO tokens to the drainer account.

Then the drainer account will deposit its ECO tokens in the Peanut contract.

Then the script will increase the inflation multiplier by 0.01 (1%). ECO inflation multiplier is being increased regularly in production.

Then the drainer will withdraw its deposit.

And voila! We have just drained / stoled ECO tokens!
