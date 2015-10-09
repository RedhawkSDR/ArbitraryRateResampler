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

    private:
        std::map<std::string, ArbitraryRateResamplerClass*>resamplers;

        void aChanged(const unsigned short *oldValue, const unsigned short *newValue);
        void outputRateChanged(const float *oldValue, const float *newValue);
        void quantizationChanged(const CORBA::ULong *oldValue, const CORBA::ULong *newValue);
        void remakeResamplers();
        void remakeResampler(float* inputRate, std::map<std::string, ArbitraryRateResamplerClass*>::iterator& i);
        std::vector<float> realOut;
        std::vector<std::complex<float> > cmplxOut;
        bool refreshSRI;
        boost::mutex resampler_mutex;
};

#endif
