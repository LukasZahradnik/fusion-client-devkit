import pathlib

import fusion
import yaml
from fusion.rest import ApiException

from utils import get_fusion_config, wait_operation_succeeded, ResourceNameReserved
import getters

def setup_infrastructure():
    print("Setting up infrastructure")

    # create an API client with your access Configuration
    config = get_fusion_config()
    client = fusion.ApiClient(config)

    # get needed API clients
    r = fusion.RegionsApi(api_client=client)
    az = fusion.AvailabilityZonesApi(api_client=client)
    se = fusion.StorageEndpointsApi(api_client=client)
    a = fusion.ArraysApi(api_client=client)
    nig = fusion.NetworkInterfaceGroupsApi(api_client=client)
    ni = fusion.NetworkInterfacesApi(api_client=client)

    # Load configuration
    with open(pathlib.Path(__file__).parent / "config/infrastructure.yaml") as file:
        infrastructure = yaml.safe_load(file)

    # Create Regions
    for region in infrastructure:
        print("Creating region", region["name"])
        current_region = fusion.RegionPost(name=region["name"], display_name=region["display_name"])
        try:
            api_response = r.create_region(current_region)
            # pprint(api_response)
            wait_operation_succeeded(api_response.id, client,resource_getter=getters.region_getter(r,current_region.name))
        except ResourceNameReserved as e:
            if not e.resource_exists:
                raise e
        except ApiException as e:
            raise RuntimeError("Exception when calling RegionsApi->create_region") from e

        # Create Availability Zones
        for availability_zone in region["availability_zones"]:
            print("Creating availability zone", availability_zone["name"], "in region", region["name"])
            current_az = fusion.AvailabilityZonePost(name=availability_zone["name"], display_name=availability_zone["display_name"])
            try:
                api_response = az.create_availability_zone(current_az, current_region.name)
                # pprint(api_response)
                wait_operation_succeeded(api_response.id, client,resource_getter=getters.availability_zone_getter(az,current_region.name,current_az.name))
            except ResourceNameReserved as e:
                if not e.resource_exists:
                    raise e
            except ApiException as e:
                raise RuntimeError("Exception when calling AvailabilityZonesApi->create_availability_zone") from e

            # Create Network Interface Groups
            for network_interface_group in availability_zone["network_interface_groups"]:
                print("Creating network interface group", network_interface_group["name"], "in availability zone", availability_zone["name"], "in region", region["name"])
                current_nig = fusion.NetworkInterfaceGroupPost(
                    name=network_interface_group["name"],
                    display_name=network_interface_group["display_name"],
                    group_type=network_interface_group["group_type"],
                    eth=fusion.NetworkInterfaceGroupEthPost(
                        prefix=network_interface_group["eth"]["prefix"],
                        mtu=network_interface_group["eth"]["mtu"]
                    )
                )
                try:
                    api_response = nig.create_network_interface_group(current_nig, current_region.name, current_az.name)
                    # pprint(api_response)
                    wait_operation_succeeded(api_response.id, client,resource_getter=getters.network_interface_groups_getter(nig,current_region.name,current_az.name,current_nig.name))
                except ResourceNameReserved as e:
                    if not e.resource_exists:
                        raise e
                except ApiException as e:
                    raise RuntimeError("Exception when calling NetworkInterfaceGroupApi->create_network_interface_group") from e

            # Create Storage Endpoints
            for storage_endpoint in availability_zone["storage_endpoints"]:
                print("Creating storage endpoint", storage_endpoint["name"], "in availability zone", availability_zone["name"], "in region", region["name"])
                current_storage_endpoint = fusion.StorageEndpointPost(
                    name=storage_endpoint["name"],
                    display_name=storage_endpoint["display_name"],
                    endpoint_type=storage_endpoint["endpoint_type"],
                    iscsi=fusion.StorageEndpointIscsiPost(
                        discovery_interfaces=[fusion.StorageEndpointIscsiDiscoveryInterface(**endpoint) for endpoint in storage_endpoint["iscsi"]]
                    )
                )
                try:
                    api_response = se.create_storage_endpoint(current_storage_endpoint, current_region.name, current_az.name)
                    # pprint(api_response)
                    wait_operation_succeeded(api_response.id, client, resource_getter=getters.storage_endpoint_getter(se,current_region.name,current_az.name,current_storage_endpoint.name))
                except ResourceNameReserved as e:
                    if not e.resource_exists:
                        raise e
                except ApiException as e:
                    raise RuntimeError("Exception when calling StorageEndpointsApi->create_storage_endpoint") from e

            # Add Arrays into Availability Zone
            for array in availability_zone["arrays"]:
                print("Creating array", array["name"], "in availability zone", availability_zone["name"], "in region", region["name"])
                current_array = fusion.ArrayPost(**array)
                try:
                    api_response = a.create_array(current_array, current_region.name, current_az.name)
                    # pprint(api_response)
                    wait_operation_succeeded(api_response.id, client, resource_getter=getters.array_getter(a,current_region.name,current_az.name,current_array.name))
                except ResourceNameReserved as e:
                    if not e.resource_exists:
                        raise e
                except ApiException as e:
                    raise RuntimeError("Exception when calling ArrayApi->create_array") from e

                print("Turning off maintenance mode on array", array["name"], "in availability zone", availability_zone["name"], "in region", region["name"])
                patch_array = fusion.ArrayPatch(maintenance_mode=fusion.NullableBoolean(False))
                try:
                    api_response = a.update_array(patch_array, current_region.name, current_az.name, array["name"])
                    # pprint(api_response)
                    wait_operation_succeeded(api_response.id, client)
                except ApiException as e:
                    raise RuntimeError("Exception when calling ArrayApi->update_array") from e

                try:
                    ni_list = ni.list_network_interfaces(current_region.name, current_az.name, array["name"])
                except ApiException as e:
                    raise RuntimeError("Exception when calling NetworkInterfacesApi->list_network_interfaces") from e

                # Add Arrays into Availability Zone
                for network_interface in ni_list.items:
                    print("Connecting network interface", network_interface.name, "on array", array["name"], "to network_interface_group", network_interface_group["name"],
                          "in availability zone", availability_zone["name"], "in region", region["name"])
                    patch_network_interface = fusion.NetworkInterfacePatch(network_interface_group=fusion.NullableString(network_interface_group["name"]))
                    try:
                        api_response = ni.update_network_interface(patch_network_interface, current_region.name, current_az.name, array["name"], network_interface.name)
                        # pprint(api_response)
                        wait_operation_succeeded(api_response.id, client)
                    except ApiException as e:
                        raise RuntimeError("Exception when calling NetworkInterfacesApi->update_network_interface") from e

    print("Done setting up infrastructure!")


if __name__ == '__main__':
    setup_infrastructure()
