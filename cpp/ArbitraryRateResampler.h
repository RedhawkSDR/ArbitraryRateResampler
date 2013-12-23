#ifndef ARBITRARYRATERESAMPLER_IMPL_H
#define ARBITRARYRATERESAMPLER_IMPL_H

#include "ArbitraryRateResampler_base.h"
#include "resampler.h"

#include <vector>
#include <boost/thread/mutex.hpp>


//redhawk component for the Arbitrary rate resampler
class ArbitraryRateResampler_i;

class ArbitraryRateResampler_i : public ArbitraryRateResampler_base
{
    ENABLE_LOGGING
    public:
        ArbitraryRateResampler_i(const char *uuid, const char *label);
        ~ArbitraryRateResampler_i();
        int serviceFunction();
        void configure (const CF::Properties& configProperties)
            throw (CF::PropertySet::PartialConfiguration,
                   CF::PropertySet::InvalidConfiguration, CORBA::SystemException);

    private:
        std::map<std::string, ArbitraryRateResamplerClass*>resamplers;

        void outputRateChanged(const std::string&);
        void quantizationChanged(const std::string&);
        void aChanged(const std::string&);
        void remakeResamplers();
        void remakeResampler(float* inputRate, std::map<std::string, ArbitraryRateResamplerClass*>::iterator& i);
        std::vector<float> realOut;
        std::vector<std::complex<float> > cmplxOut;
        bool refreshSRI;
        boost::mutex resampler_mutex;
};

#endif
