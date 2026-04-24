#include <cppmicroservices/Framework.h>
#include <cppmicroservices/FrameworkFactory.h>
#include <cppmicroservices/FrameworkEvent.h>

int main()
{
    auto framework = cppmicroservices::FrameworkFactory().NewFramework();
    framework.Start();
    framework.Stop();
    framework.WaitForStop(std::chrono::milliseconds(0));
    return 0;
}
