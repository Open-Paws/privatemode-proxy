# Quickstart: Create confidential VM in the Azure portal

> **Source:** <https://learn.microsoft.com/en-us/azure/confidential-computing/quick-create-confidential-vm-portal>

You can use the Azure portal to create a confidential VM based on an Azure Marketplace image quickly. There are multiple confidential VM options on AMD and Intel with AMD SEV-SNP and Intel TDX technology.

## Prerequisites

- An Azure subscription. Free trial accounts don't have access to the VMs used in this tutorial. One option is to use a pay as you go subscription.

- If you're using a Linux-based confidential VM, use a BASH shell for SSH or install an SSH client, such as PuTTY.

- If Confidential disk encryption with a customer-managed key is required, please run below command to opt in service principal Confidential VM Orchestrator to your tenant. Install Microsoft Graph SDK to execute the commands below.

```powershell
Connect-Graph -Tenant "your tenant ID" Application.ReadWrite.All
New-MgServicePrincipal -AppId bf7b6499-ff71-4aa2-97a4-f372087be7f0 -DisplayName "Confidential VM Orchestrator"
```

## Create confidential VM

To create a confidential VM in the Azure portal using an Azure Marketplace image:

1. Sign in to the Azure portal.

2. Select or search for **Virtual machines**.

3. On the Virtual machines page menu, select **Create > Virtual machine**.

4. On the tab **Basics**, configure the following settings:

   a. Under **Project details**, for **Subscription**, select an Azure subscription that meets the prerequisites.

   b. For **Resource Group**, select **Create new** to create a new resource group. Enter a name, and select **OK**.

   c. Under **Instance details**, for **Virtual machine name**, enter a name for your new VM.

   d. For **Region**, select the Azure region in which to deploy your VM.

   > **Note:** Confidential VMs are not available in all locations. For currently supported locations, see which VM products are available by Azure region.

   e. For **Availability options**, select **No infrastructure redundancy required** for singular VMs or **Virtual machine scale set** for multiple VMs.

   f. For **Security Type**, select **Confidential virtual machines**.

   g. For **Image**, select the OS image to use for your VM. Select **See all images** to open Azure Marketplace. Select the filter **Security Type > Confidential** to show all available confidential VM images.

   h. Toggle **Generation 2** images. Confidential VMs only run on Generation 2 images. To ensure, under **Image**, select **Configure VM generation**. In the pane **Configure VM generation**, for **VM generation**, select **Generation 2**. Then, select **Apply**.

   > **Note:** For NCCH100v5 series, only the Ubuntu Server 22.04 LTS (Confidential VM) image is currently supported.

   i. For **Size**, select a VM size. For more information, see supported confidential VM families.

   j. For **Authentication type**, if you're creating a Linux VM, select **SSH public key**. If you don't already have SSH keys, create SSH keys for your Linux VMs.

   k. Under **Administrator account**, for **Username**, enter an administrator name for your VM.

   l. For **SSH public key**, if applicable, enter your RSA public key.

   m. For **Password** and **Confirm password**, if applicable, enter an administrator password.

   n. Under **Inbound port rules**, for **Public inbound ports**, select **Allow selected ports**.

   o. For **Select inbound ports**, select your inbound ports from the drop-down menu. For Windows VMs, select **HTTP (80)** and **RDP (3389)**. For Linux VMs, select **SSH (22)** and **HTTP (80)**.

   > **Note:** It's not recommended to allow RDP/SSH ports for production deployments.

5. On the tab **Disks**, configure the following settings:

   - Under **Disk options**, enable **Confidential OS disk encryption** if you want to encrypt your VM's OS disk during creation.

   - For **Key Management**, select the type of key to use.

   - If **Confidential disk encryption with a customer-managed key** is selected, create a **Confidential disk encryption set** before creating your confidential VM.

   - If you want to encrypt your VM's temp disk, please refer to the following documentation.

6. (Optional) If necessary, you need to create a **Confidential disk encryption set** as follows:

   a. Create an Azure Key Vault using the **Premium** pricing tier that includes support for HSM-backed keys. It's also important to enable purge protection for added security measures. Additionally, for the access configuration, use the "Vault access policy" under "Access configuration" tab. Alternatively, you can create an Azure Key Vault managed Hardware Security Module (HSM).

   b. In the Azure portal, search for and select **Disk Encryption Sets**.

   c. Select **Create**.

   d. For **Subscription**, select which Azure subscription to use.

   e. For **Resource group**, select or create a new resource group to use.

   f. For **Disk encryption set name**, enter a name for the set.

   g. For **Region**, select an available Azure region.

   h. For **Encryption type**, select **Confidential disk encryption with a customer-managed key**.

   i. For **Key Vault**, select the key vault you already created.

   j. Under **Key Vault**, select **Create new** to create a new key.

   > **Note:** If you selected an Azure managed HSM previously, use PowerShell or the Azure CLI to create the new key instead.

   k. For **Name**, enter a name for the key.

   l. For the **key type**, select **RSA-HSM**

   m. Select your **key size**

   n. Under **Confidential Key Options** select **Exportable** and set the **Confidential operation policy** as **CVM confidential operation policy**.

   o. Select **Create** to finish creating the key.

   p. Select **Review + create** to create new disk encryption set. Wait for the resource creation to complete successfully.

   q. Go to the disk encryption set resource in the Azure portal.

   r. When you see a blue info banner, please follow the instructions provided to grant access. On encountering a pink banner, simply select it to grant the necessary permissions to Azure Key Vault.

   > **Important:** You must perform this step to successfully create the confidential VM.

7. As needed, make changes to settings under the tabs **Networking**, **Management**, **Guest Config**, and **Tags**.

8. Select **Review + create** to validate your configuration.

9. Wait for validation to complete. If necessary, fix any validation issues, then select **Review + create** again.

10. In the **Review + create** pane, select **Create**.

## Connect to confidential VM

There are different methods to connect to Windows confidential VMs and Linux confidential VMs.

### Connect to Windows VMs

To connect to a confidential VM with a Windows OS, see How to connect and sign on to an Azure virtual machine running Windows.

### Connect to Linux VMs

To connect to a confidential VM with a Linux OS, see the instructions for your computer's OS.

Before you begin, make sure you have your VM's public IP address. To find the IP address:

1. Sign in to the Azure portal.

2. Select or search for **Virtual machines**.

3. On the Virtual machines page, select your confidential VM.

4. On your confidential VM's overview page, copy the **Public IP address**.

For more information about connecting to Linux VMs, see Quickstart: Create a Linux virtual machine in the Azure portal.

#### Using SSH

1. Open your SSH client, such as PuTTY.

2. Enter your confidential VM's public IP address.

3. Connect to the VM. In PuTTY, select **Open**.

4. Enter your VM administrator username and password.

> **Note:** If you're using PuTTY, you might receive a security alert that the server's host key isn't cached in the registry. If you trust the host, select **Yes** to add the key to PuTTY's cache and continue connecting. To connect just once, without adding the key, select **No**. If you don't trust the host, select **Cancel** to abandon your connection.

## Clean up resources

After you're done with the quickstart, you can clean up the confidential VM, the resource group, and other related resources.

1. Sign in to the Azure portal.

2. Select or search for **Resource groups**.

3. On the Resource groups page, select the resource group you created for this quickstart.

4. On the resource group's menu, select **Delete resource group**.

5. In the warning pane, enter the resource group's name to confirm the deletion.

6. Select **Delete**.

## Next steps

- Learn about [confidential VM options](virtual-machine-options.md)
- Explore [guest attestation](guest-attestation-confidential-vms.md)
- Review the [confidential VM FAQ](confidential-vm-faq.md)

*Last updated: 06/27/2024*
*Last scraped: 2025-12-04*
