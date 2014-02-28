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
/**************************************************************************

    This is the component code. This file contains the child class where
    custom functionality can be added to the component. Custom
    functionality to the base class can be extended here. Access to
    the ports can also be done from this class

**************************************************************************/

#include "ArbitraryRateResampler.h"

PREPARE_LOGGING(ArbitraryRateResampler_i)

ArbitraryRateResampler_i::ArbitraryRateResampler_i(const char *uuid, const char *label) :
    ArbitraryRateResampler_base(uuid, label),
    refreshSRI(false)
{
	//set-up property callbacks
	setPropertyChangeListener("outputRate", this, &ArbitraryRateResampler_i::outputRateChanged);
	setPropertyChangeListener("quantization", this, &ArbitraryRateResampler_i::quantizationChanged);
	setPropertyChangeListener("a", this, &ArbitraryRateResampler_i::aChanged);

}

ArbitraryRateResampler_i::~ArbitraryRateResampler_i()
{
	//delete  all our resamplers to avoid a memory leak
	for (std::map<std::string, ArbitraryRateResamplerClass*>::iterator i = resamplers.begin(); i!=resamplers.end(); i++)
		delete i->second;
}

void ArbitraryRateResampler_i::configure (const CF::Properties& configProperties)
    throw (CF::PropertySet::PartialConfiguration,
           CF::PropertySet::InvalidConfiguration, CORBA::SystemException)
{
    //override configure to keep the service function from executing in the midst of a configure
	boost::mutex::scoped_lock lock(resampler_mutex);
	ArbitraryRateResampler_base::configure(configProperties);
}

int ArbitraryRateResampler_i::serviceFunction()
{
    //keep the service function from executing in the midst of a configure
	LOG_DEBUG(ArbitraryRateResampler_i, "serviceFunction() example log message");

	//Get data
    bulkio::InFloatPort::dataTransfer *tmp = dataFloat_in->getPacket(bulkio::Const::BLOCKING);
	if (not tmp) { // No data is available
		return NOOP;
	}
	if (tmp->inputQueueFlushed)
	{
		LOG_WARN(ArbitraryRateResampler_i, "input Q flushed - data has been thrown on the floor.  flushing internal buffers");
		//flush all our processor states if the Q flushed
		remakeResamplers();
	}

	boost::mutex::scoped_lock lock(resampler_mutex);

	//get metadata from the sri that we will need for processing
	float inputRate = 1.0/tmp->SRI.xdelta;
	std::string streamID(tmp->SRI.streamID.in());

	//force an SRI update for this stream if we have never seen this stream before or this sriChanged and we aren't updating all the sris
	bool forceThisSriUpdate = (resamplers.count(streamID)==0 || (tmp->sriChanged  && !refreshSRI));
	if (refreshSRI)
	{
		//if we were told to refresh all the SRIs - then do it - update the output sample rate at the same time to reflect our property value!
		float xdelta = 1.0/outputRate;
		std::map< std::string, std::pair< BULKIO::StreamSRI, bool > > currentSRI;
		currentSRI = dataFloat_out->getCurrentSRI();
		for (std::map< std::string, std::pair< BULKIO::StreamSRI, bool > >::iterator i = currentSRI.begin(); i!=currentSRI.end(); i++)
		{
			i->second.first.xdelta = xdelta;
			dataFloat_out->pushSRI(i->second.first);
		}
		refreshSRI=false;
	}
	if (forceThisSriUpdate)
	{
		//just send this stream sri if required
		tmp->SRI.xdelta = 1.0/outputRate;
		dataFloat_out->pushSRI(tmp->SRI);
	}

	//find our resampler
	std::map<std::string, ArbitraryRateResamplerClass*>::iterator i = resamplers.find(streamID);
	if (i==resamplers.end())
	{
		//we don't have a resampler for this stream yet - create a new one and insert it into our container
		//std::cout<<"new resampler inputRate "<< inputRate<<", outputRate "<< outputRate<<", a "<<a<<", quantization "<<quantization<< std::endl;
		ArbitraryRateResamplerClass* ptr = new ArbitraryRateResamplerClass(inputRate, outputRate, a, quantization, realOut, cmplxOut);
		i=resamplers.insert(resamplers.end(), std::pair<std::string,ArbitraryRateResamplerClass*>(streamID, ptr));
	}
	//get the resampler from the iterator to use bellow
	ArbitraryRateResamplerClass* resampler=i->second;

	//check the data rate to make sure it is OK and regenerate a new resampler if it has changed
	if (resampler->getInRate()!=inputRate)
	{
		remakeResampler(&inputRate, i);
		resampler=i->second;
	}

	//this is the delay (in seconds) we will need to update our timecode by
	float delay;
	//now do the resampling
	if (tmp->SRI.mode==1)
	{
		//data is complex - send complex data to the resmpler class
		std::vector<std::complex<float> >* cxInput = reinterpret_cast<std::vector<std::complex<float> >* > (&tmp->dataBuffer);
		delay=resampler->newData(*cxInput);
	}
	else
	{
		//data is real - send real data to the resmpler class
		delay=resampler->newData(tmp->dataBuffer);
	}

	//If we are done with the stream - delete the resampler and remove the iterator from the container
	if (tmp->EOS)
	{
		delete resampler;
		resamplers.erase(i);
	}

    //send the output
	bool haveSentTimeStamp=false;

	//adjust offset to take into account the different sample rate and additional filter delay
	tmp->T.toff = (tmp->T.toff/inputRate + delay)*outputRate;

	//send the output - if we have any complex data it goes first
	if (!cmplxOut.empty())
	{
		if (tmp->SRI.mode==0)
		{
			//case where the input is real and the output is complex means we had complex data in our history buffer
			//update the sri right now to let downstream know we are sending complex data
			tmp->SRI.mode=1;
			dataFloat_out->pushSRI(tmp->SRI);
		}
		haveSentTimeStamp=true;
		std::vector<float>* tmpVec = reinterpret_cast<std::vector<float>* >(&cmplxOut);
		dataFloat_out->pushPacket(*tmpVec, tmp->T, tmp->EOS, tmp->streamID);
	}
	//now if we have any real data send it
	if (!realOut.empty())
	{
		//if the sri was complex from last push - update to real and pushSRI
		if (tmp->SRI.mode==1)
		{
			tmp->SRI.mode=0;
			dataFloat_out->pushSRI(tmp->SRI);
		}
		//If we sent a timestamp already the time in the timestamp points to the previous data sample
		//update the timestamp to be invalid so subsigquent processors realize it is bogus and can be disregarded
		if (haveSentTimeStamp)
			tmp->T.tcstatus =BULKIO::TCS_INVALID;
		dataFloat_out->pushPacket(realOut, tmp->T, tmp->EOS, tmp->streamID);
	}

	//we are all done - delete the data packet and return norml
	delete tmp;
    return NORMAL;
}

void ArbitraryRateResampler_i::outputRateChanged(const std::string&)
{
	//if the output changes we must remake the resamplers and refresh the SRI to let downstream people know we have a new sample rate
	remakeResamplers();
    refreshSRI=true;
}
void ArbitraryRateResampler_i::quantizationChanged(const std::string&)
{
	remakeResamplers();
}
void ArbitraryRateResampler_i::aChanged(const std::string&)
{
	remakeResamplers();
}

void ArbitraryRateResampler_i::remakeResamplers()
{
	//remake all the resamplers using the default inputRate for each stream
	for (std::map<std::string, ArbitraryRateResamplerClass*>::iterator i = resamplers.begin(); i!=resamplers.end(); i++)
		remakeResampler(NULL, i);
}

void ArbitraryRateResampler_i::remakeResampler(float* inputRate, std::map<std::string, ArbitraryRateResamplerClass*>::iterator& i)
{
	//if we don't have an inputRate - use the previous inputRate and keep
	std::deque<float>* realHistory=NULL;
	std::deque<std::complex<float> >* cmplxHistory=NULL;
	float startTime = i->second->getNextOutputDelay();
	float tmp;
	if (inputRate==NULL)
	{
		//if the inputRate is not given to us it has not changed
		//we use the previous inputRate and history
		//we don't use the previous history if the sample rate changes as those samples are not valid at our new input rate

		inputRate=&tmp;
		*inputRate = i->second->getInRate();
		realHistory =i->second->getRealHistory();
		cmplxHistory =i->second->getComplexHistory();
	}
	//std::cout<<"inputRate "<< (*inputRate)<<", outputRate "<< outputRate<<", a "<<a<<", quantization "<<quantization<< std::endl;
	ArbitraryRateResamplerClass* ptr = new ArbitraryRateResamplerClass(*inputRate, outputRate, a, quantization, realOut, cmplxOut, &startTime, realHistory, cmplxHistory);
	//delete the old instance
	delete i->second;
	//set the pointer for the container to use the new instance
	i->second = ptr;
}
