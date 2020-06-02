from os import environ
from models.constants import INSTANCE_CATEGORIES
from re import search, IGNORECASE
import openstack

VALID_IMAGES = r"centos"
AUTO_ALLOCATED_IP_LABEL = "Automatic allocation"

# Magic Castle requires 10 GB on the root disk for each node.
# Otherwise, it creates and mounts an external volume of 10 GB.
MINIMUM_ROOT_DISK_SIZE = 10


class OpenStackManager:
    def __init__(
        self, *, pre_allocated_cores=0, pre_allocated_ram=0, pre_allocated_volume_size=0
    ):
        self.__connection = openstack.connect()
        self.__pre_allocated_cores = pre_allocated_cores
        self.__pre_allocated_ram = pre_allocated_ram
        self.__pre_allocated_volume_size = pre_allocated_volume_size

        self.__volume_quotas = None
        self.__compute_quotas = None

        self.__available_flavors = None

    def get_available_resources(self):
        return {
            "quotas": self.__get_quotas(),
            "resource_details": self.__get_resource_details(),
            "possible_resources": self.__get_possible_resources(),
        }

    def get_available_floating_ips(self):
        return [
            ip.floating_ip_address
            for ip in self.__connection.network.ips(status="DOWN")
        ]

    def __get_quotas(self):
        return {
            "ram": {"max": self.__get_available_ram()},
            "vcpus": {"max": self.__get_available_vcpus()},
            "volume_storage": {"max": self.__get_available_volume_size()},
        }

    def __get_possible_resources(self):
        flavors = list(map(lambda flavor: flavor.name, self.__get_available_flavors()))
        floating_ips = self.get_available_floating_ips() + [AUTO_ALLOCATED_IP_LABEL]
        return {
            "image": self.__get_images(),
            "instances": {
                category: {"type": flavors} for category in INSTANCE_CATEGORIES
            },
            "os_floating_ips": floating_ips,
            "storage": {"type": ["nfs"]},
        }

    def __get_resource_details(self):
        return {
            "instance_types": [
                {
                    "name": flavor.name,
                    "vcpus": flavor.vcpus,
                    "ram": flavor.ram,
                    "required_volume_storage": MINIMUM_ROOT_DISK_SIZE
                    if flavor.disk < MINIMUM_ROOT_DISK_SIZE
                    else 0,
                }
                for flavor in self.__get_available_flavors()
            ]
        }

    def __get_images(self):
        return [
            image.name
            for image in self.__connection.image.images()
            if search(VALID_IMAGES, image.name, IGNORECASE)
        ]

    def __get_available_flavors(self):
        if self.__available_flavors is None:
            self.__available_flavors = [
                flavor
                for flavor in self.__connection.compute.flavors()
                if flavor.ram <= self.__get_available_ram()
                and flavor.vcpus <= self.__get_available_vcpus()
            ]
            self.__available_flavors.sort(key=lambda flavor: (flavor.ram, flavor.vcpus))
        return self.__available_flavors

    def __get_available_ram(self):
        return (
            self.__pre_allocated_ram
            + self.__get_compute_quotas()["ram"]["limit"]
            - self.__get_compute_quotas()["ram"]["in_use"]
        )

    def __get_available_vcpus(self):
        return (
            self.__pre_allocated_cores
            + self.__get_compute_quotas()["cores"]["limit"]
            - self.__get_compute_quotas()["cores"]["in_use"]
        )

    def __get_available_volume_size(self):
        return (
            self.__pre_allocated_volume_size
            + self.__get_volume_quotas()["gigabytes"]["limit"]
            - self.__get_volume_quotas()["gigabytes"]["in_use"]
        )

    def __get_volume_quotas(self):
        if self.__volume_quotas is None:
            # Normally, we should use self.__connection.get_volume_quotas(...) from openstack sdk.
            # However, this method executes the action
            # identity:list_projects from the identity api which is forbidden
            # to some users.
            #
            # API documentation:
            # https://docs.openstack.org/api-ref/block-storage/v3/index.html?expanded=show-quotas-for-a-project-detail#show-quotas-for-a-project
            self.__volume_quotas = self.__connection.block_storage.get(
                f"/os-quota-sets/{environ['OS_PROJECT_ID']}?usage=true"
            ).json()["quota_set"]
        return self.__volume_quotas

    def __get_compute_quotas(self):
        if self.__compute_quotas is None:
            # Normally, we should use self.__connection.get_compute_quotas(...) from openstack sdk.
            # However, this method executes the action
            # identity:list_projects from the identity api which is forbidden
            # to some users.
            #
            # API documentation:
            # https://docs.openstack.org/api-ref/compute/?expanded=show-a-quota-detail#show-a-quota
            self.__compute_quotas = self.__connection.compute.get(
                f"/os-quota-sets/{environ['OS_PROJECT_ID']}/detail"
            ).json()["quota_set"]
        return self.__compute_quotas
