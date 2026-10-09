# ./bin/lencod_static -d ./cfg/encoder.cfg -p InputFile="./jm_data/fern_1008x756_20.yuv" -p OutputFile="./jm_data/fern_enc_ai.264" \
#         -p ReconFile="./jm_data/fern_recon_ai.yuv" -p SourceWidth=1008 -p SourceHeight=756 -p OutputWidth=1008 -p OutputHeight=756 \
#         -p QPISlice=32 -p IntraPeriod=1 -p NumberBFrames=0 -p FramesToBeEncoded=20 \
#         | tee ./jm_data/fern_ai_log.txt

# ./bin/ldecod_static -d ./cfg/decoder.cfg -p DeblockDir="./jm_data/deblock_ai" -p ResidualDir="./jm_data/residual_ai" \
        # -p OutputFile="./jm_data/fern_dec_ai.264" -p RefFile="./jm_data/fern_recon_ai.yuv" -p InputFile="./jm_data/fern_enc_ai.264" 

./bin/lencod_static -d ./cfg/encoder.cfg -p InputFile="./jm_data/fern_1008x756_20.yuv" -p OutputFile="./jm_data/fern_enc_ra.264" \
        -p ReconFile="./jm_data/fern_recon_ra.yuv" -p SourceWidth=1008 -p SourceHeight=756 -p OutputWidth=1008 -p OutputHeight=756 \
        -p QPISlice=32 -p QPPSlice=32 -p QPBSlice=32 -p IntraPeriod=32 -p NumberBFrames=7 -p FramesToBeEncoded=20 \
        | tee ./jm_data/fern_ra_log.txt

# ./bin/ldecod_static -d ./cfg/decoder.cfg -p DeblockDir="./jm_data/deblock_ra" -p ResidualDir="./jm_data/residual_ra" \
        # -p OutputFile="./jm_data/fern_dec_ra.264" -p RefFile="./jm_data/fern_recon_ra.yuv" -p InputFile="./jm_data/fern_enc_ra.264"