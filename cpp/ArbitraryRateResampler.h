/*
 * This file is protected by Copyright. Please refer to the COPYRIGHT file distributed with this
 * source distribution.
 *
 * This file is part of REDHAWK Basic Components ArbitraryRateResampler.
 *
 * REDHAWK Basic Components ArbitraryRateResampler is free software: you can redistribute it and/or modify it under the terms of
 * the GNU Lesser General Public License as published by the Free Software Foundation, either
 * version 3 of the License, or (at your option) any later version.
 *
 * REDHAWK Basic Components ArbitraryRateResampler is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
 * without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
 * PURPOSE.  See the GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License along with this
 * program.  If not, see http://www.gnu.org/licenses/.
 */
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
