"""
This file is part of nucypher.

nucypher is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

nucypher is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with nucypher.  If not, see <https://www.gnu.org/licenses/>.

"""


import collections
import os

import click
from constant_sorrow.constants import NO_PASSWORD, NO_BLOCKCHAIN_CONNECTION
from nacl.exceptions import CryptoError
from twisted.logger import Logger
from twisted.logger import globalLogPublisher

from nucypher.blockchain.eth.registry import EthereumContractRegistry
from nucypher.config.constants import NUCYPHER_SENTRY_ENDPOINT
from nucypher.config.node import NodeConfiguration
from nucypher.utilities.logging import (
    logToSentry,
    getTextFileObserver,
    initialize_sentry,
    getJsonFileObserver
)


class NucypherClickConfig:

    # Output Sinks
    capture_stdout = False
    __emitter = None
    __sentry_endpoint = NUCYPHER_SENTRY_ENDPOINT

    # Environment Variables
    config_file = os.environ.get('NUCYPHER_CONFIG_FILE')
    sentry_endpoint = os.environ.get("NUCYPHER_SENTRY_DSN", __sentry_endpoint)
    log_to_sentry = os.environ.get("NUCYPHER_SENTRY_LOGS", True)
    log_to_file = os.environ.get("NUCYPHER_FILE_LOGS", True)

    # Sentry Logging
    if log_to_sentry is True:
        initialize_sentry(dsn=__sentry_endpoint)
        globalLogPublisher.addObserver(logToSentry)

    # File Logging
    if log_to_file is True:
        globalLogPublisher.addObserver(getTextFileObserver())
        globalLogPublisher.addObserver(getJsonFileObserver())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Logging
        self.quiet = False
        self.log = Logger(self.__class__.__name__)

        # Auth
        self.__keyring_password = NO_PASSWORD

        # Blockchain
        self.accounts = NO_BLOCKCHAIN_CONNECTION
        self.blockchain = NO_BLOCKCHAIN_CONNECTION

    def connect_to_blockchain(self, character_configuration, recompile_contracts: bool = False):
        try:
            character_configuration.connect_to_blockchain(recompile_contracts=recompile_contracts)
            character_configuration.connect_to_contracts()
        except EthereumContractRegistry.NoRegistry:
            message = "No contract registry found; Did you mean to pass --federated-only?"
            raise EthereumContractRegistry.NoRegistry(message)

        else:
            self.blockchain = character_configuration.blockchain
            self.accounts = self.blockchain.interface.w3.eth.accounts

    def get_password(self, confirm: bool = False) -> str:
        keyring_password = os.environ.get("NUCYPHER_KEYRING_PASSWORD", NO_PASSWORD)

        if keyring_password is NO_PASSWORD:  # Collect password, prefer env var
            prompt = "Enter keyring password"
            keyring_password = click.prompt(prompt, confirmation_prompt=confirm, hide_input=True)

        self.__keyring_password = keyring_password
        return self.__keyring_password

    def unlock_keyring(self, character_configuration: NodeConfiguration):
        try:  # Unlock Keyring
            if not self.quiet:
                self.emit(message='Decrypting keyring...', color='blue')
            character_configuration.keyring.unlock(password=self.get_password())  # Takes ~3 seconds, ~1GB Ram
        except CryptoError:
            raise character_configuration.keyring.AuthenticationFailed

    @classmethod
    def attach_emitter(cls, emitter) -> None:
        cls.__emitter = emitter

    @classmethod
    def emit(cls, *args, **kwargs):
        cls.__emitter(*args, **kwargs)


class NucypherDeployerClickConfig(NucypherClickConfig):

    __secrets = ('miner_secret', 'policy_secret', 'escrow_proxy_secret', 'mining_adjudicator_secret')
    Secrets = collections.namedtuple('Secrets', __secrets)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Deployment Environment Variables
        self.miner_escrow_deployment_secret = os.environ.get("NUCYPHER_MINER_ESCROW_SECRET")
        self.policy_manager_deployment_secret = os.environ.get("NUCYPHER_POLICY_MANAGER_SECRET")
        self.user_escrow_proxy_deployment_secret = os.environ.get("NUCYPHER_USER_ESCROW_PROXY_SECRET")
        self.mining_adjudicator_deployment_secret = os.environ.get("NUCYPHER_MINING_ADJUDICATOR_SECRET")

    def collect_deployment_secrets(self) -> Secrets:

        if not self.miner_escrow_deployment_secret:
            self.miner_escrow_deployment_secret = click.prompt('Enter MinerEscrow Deployment Secret',
                                                               hide_input=True,
                                                               confirmation_prompt=True)

        if not self.policy_manager_deployment_secret:
            self.policy_manager_deployment_secret = click.prompt('Enter PolicyManager Deployment Secret',
                                                                 hide_input=True,
                                                                 confirmation_prompt=True)

        if not self.user_escrow_proxy_deployment_secret:
            self.user_escrow_proxy_deployment_secret = click.prompt('Enter UserEscrowProxy Deployment Secret',
                                                                    hide_input=True,
                                                                    confirmation_prompt=True)

        if not self.mining_adjudicator_deployment_secret:
            self.mining_adjudicator_deployment_secret = click.prompt('Enter MiningAdjudicator Deployment Secret',
                                                                     hide_input=True,
                                                                     confirmation_prompt=True)

        secrets = self.Secrets(miner_secret=self.miner_escrow_deployment_secret,                    # type: str
                               policy_secret=self.policy_manager_deployment_secret,                 # type: str
                               escrow_proxy_secret=self.user_escrow_proxy_deployment_secret,        # type: str
                               mining_adjudicator_secret=self.mining_adjudicator_deployment_secret  # type: str
                               )
        return secrets


# Register the above click configuration classes as a decorators
nucypher_click_config = click.make_pass_decorator(NucypherClickConfig, ensure=True)
nucypher_deployer_config = click.make_pass_decorator(NucypherDeployerClickConfig, ensure=True)
