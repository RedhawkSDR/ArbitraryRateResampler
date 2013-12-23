#include <iostream>
#include "ossie/ossieSupport.h"

#include "ArbitraryRateResampler.h"


int main(int argc, char* argv[])
{
    ArbitraryRateResampler_i* ArbitraryRateResampler_servant;
    Resource_impl::start_component(ArbitraryRateResampler_servant, argc, argv);
    return 0;
}
