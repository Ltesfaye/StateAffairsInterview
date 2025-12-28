# State Affairs Technical Challenge


The Michigan Legislature holds public hearings on a regular basis while in session. After a hearing concludes, a recording is published to one of the following public portals:

* Michigan House:https://house.mi.gov/VideoArchive

* Michigan Senate:https://cloud.castus.tv/vod/misenate/?page=ALL


# Task


Build a system that can be executed on a schedule (e.g., via cron) with the following responsibilities:

* Detect newly published hearing videos on the House and Senate archives.

* Download any new videos that have not yet been processed. You do not need to scrape all historical videos. The last 1-2 months of hearings should be more than enough for us to discuss your approach.

* Transcribe the contents of the downloaded videos.

* Handle failures gracefully and ensure the system can recover without manual intervention.

 

# Requirements


* The system should be designed to run periodically and be safe to invoke multiple times.

* It should track previously processed videos to avoid re-downloading or re-transcribing the same content.

* Transcription can be performed locally or through a third-party service.

* The code should be modular, well-structured, and production-quality.

 

# Notes


You are welcome to use any tooling or libraries during development. However, during the interview discussion, you will not have access to AI assistance. Be prepared to explain and reason through your implementation decisions.

Please share a link to a private github repository with github account @FredLoh ( https://github.com/FredLoh ) As a reminder, please be sure to submit your completed exercise at least 24 hours prior to your onsite interview.

