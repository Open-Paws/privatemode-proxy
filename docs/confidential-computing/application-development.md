# Application enclaves

> **Source:** <https://learn.microsoft.com/en-us/azure/confidential-computing/application-development>

*Use tools and libraries to develop applications for confidential computing on Intel SGX*

Application enclaves, such as Intel SGX, are isolated environments that protect specific code and data. When creating enclaves, you must determine what part of the application runs within the enclave. When you create or manage enclaves, be sure to use compatible SDKs and frameworks for the chosen deployment stack.

If you haven't already read the [introduction to Intel SGX VMs and enclaves](confidential-computing-enclaves), do so before continuing.

## Microsoft Mechanics

### Developing applications

There are two partitions in an application built with enclaves.

The **host** is the "untrusted" component. Your enclave application runs on top of the host. The host is an untrusted environment. When you deploy enclave code on the host, the host can't access that code.

The **enclave** is the "trusted" component. The application code and its cached data and memory run in the enclave. The enclave environment protects your secrets and sensitive data. Make sure your secure computations happen in an enclave.

![Diagram of an application, showing the host and enclave partitions. Inside the enclave are the data and application code components.](media/application-development/oe-sdk.png)

To use the power of enclaves and isolated environments, choose tools that support confidential computing. Various tools support enclave application development. For example, you can use these open-source frameworks:

* [The Open Enclave Software Development Kit (OE SDK)](enclave-development-oss#oe-sdk)
* [The Intel SGX SDK](enclave-development-oss#intel-sdk)
* [The EGo Software Development Kit](enclave-development-oss#ego)
* [The Confidential Consortium Framework (CCF)](enclave-development-oss#ccf)

As you design an application, identify and determine what part of needs to run in enclaves. Code in the trusted component is isolated from the rest of your application. After the enclave initializes and the code loads to memory, untrusted components can't read or change that code.

## Next steps

* [Start developing applications with open-source software](enclave-development-oss)
*Last scraped: 2025-12-04*
