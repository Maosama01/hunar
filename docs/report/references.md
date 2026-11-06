# Hunar: Verified References

Bibliography for the Hunar minor-project report (SIH26242, MSDE): AI-assisted Recognition of Prior Learning (RPL) for Indian informal workers.

**How this list was verified (checked on 28 Oct 2026).** Every entry below was checked against a live source and was not written from memory. Journal and conference papers were checked through the Crossref REST API (`https://api.crossref.org/works/<DOI>`), the ACL Anthology, arXiv, PMLR, NeurIPS proceedings or PubMed. Government and agency documents were opened on the official site (nqr.gov.in, ncvet.gov.in, msde.gov.in, mospi.gov.in, ugc.gov.in, unesdoc.unesco.org, ilo.org), and their title pages were read. Fields that could not be confirmed, such as some volume numbers, places of publication and gazette part/section numbers, were left out on purpose. Entries are in IEEE style. BibTeX keys match `references.bib`.

---

## 1. RPL, NSQF and the Indian skills ecosystem

**[1] `mof2013nsqf`**
Ministry of Finance (Department of Economic Affairs), Government of India, "National Skills Qualification Framework (NSQF)," Notification No. 8/6/2013-Invt., New Delhi, Dec. 27, 2013.
- URL: https://nqr.gov.in/nsqf
- Verified: https://nqr.gov.in/nsqf (says the NSQF "was notified on 27th Dec 2013" after Cabinet Committee approval on 19 Dec 2013). The notification number and issuing department are cited in the NSQF-2023 text at https://nqr.gov.in/downloads/pdfs/NSQF_Gazette_Notification.pdf (§2.2).
- Relevance: This is the original legal basis for NSQF levels and learning-outcome-based qualifications, which Hunar maps worker declarations onto.

**[2] `ncvet2023nsqf`**
National Council for Vocational Education and Training, Ministry of Skill Development and Entrepreneurship, Government of India, "National Skills Qualification Framework-2023," F. No. 22001/01/2023/NCVET, 2023. [Online]. Available: https://nqr.gov.in/downloads/pdfs/NSQF_Gazette_Notification.pdf
- Verified: https://nqr.gov.in/downloads/pdfs/NSQF_Gazette_Notification.pdf (header and §1 read; the PDF's title metadata gives June 2023; the text says it supersedes the 27 Dec 2013 notification).
- Relevance: This is the current revised NSQF. It formally defines "Recognition of Prior Learning" as assessment and certification of people who already have prior learning or skills, which is the process Hunar supports.

**[3] `msde2018ncvet`**
Ministry of Skill Development and Entrepreneurship, Government of India, Gazette Notification No. SD-17/113/2017-E&PW (constituting the National Council for Vocational Education and Training), Dec. 5, 2018.
- URL: https://ncvet.gov.in/about-ncvet/
- Verified: https://ncvet.gov.in/about-ncvet/ (states NCVET was established through this notification dated 5 Dec 2018 and has been fully operational since 1 Aug 2020).
- Relevance: It establishes NCVET as the regulator for awarding and assessment bodies, so it sets the institutional context in which Hunar's assessor-facing tool would operate.

**[4] `ncvet2023rpl`**
National Council for Vocational Education and Training (NCVET), "Guidelines for Recognition of Prior Learning (RPL)," New Delhi, India, Aug. 11, 2023. [Online]. Available: https://ncvet.gov.in/wp-content/uploads/2023/08/Final-RPL-guidelines.pdf
- Verified: the PDF at the URL above was downloaded and its title page read (title, date 11 August 2023, issuing body NCVET). The guidelines page is https://ncvet.gov.in/guidelines/
- Relevance: This is the operative Indian RPL guideline. Its sections on portfolio evidence, online/offline on-demand assessment and a dedicated RPL digital portal match Hunar's evidence-capture and assessor workflow.

**[5] `ugc2023ncrf`**
University Grants Commission, "National Credit Framework (NCrF): Report of the High-Level Committee comprising members from UGC, AICTE, NCVET, DoSEL & DoHE (MoE), MSDE, CBSE, NCERT, NIOS and DGT," New Delhi, India, Apr. 2023. [Online]. Available: https://www.ugc.gov.in/pdfnews/9028476_Report-of-National-Credit-Framework.pdf
- Verified: the PDF at the URL above was downloaded and its cover and imprint pages read (April 2023; published by the Secretary, UGC, New Delhi).
- Relevance: The NCrF integrates NSQF levels with academic credit and contains RPL provisions, so it shows how Hunar-supported RPL outcomes could carry credit.

**[6] `msdepmkvy4`**
Ministry of Skill Development and Entrepreneurship, Government of India, "Guidelines for Pradhan Mantri Kaushal Vikas Yojana 4.0," n.d. [Online]. Available: https://www.msde.gov.in/static/uploads/2024/02/PMKVY-4.0-Guidelines_final-copy.pdf
- Verified: the PDF at the URL above was downloaded and its cover and contents read. It has a section titled "Recognition of Prior Learning – Project Implementing Agency (RPL-PIA)" and "Pay-out mechanism – Recognition of Prior Learning (RPL)." No publication date is printed, so the date is given as n.d.
- Relevance: PMKVY's RPL component is the main government channel through which informal workers are assessed and certified at scale, and Hunar's workflow is designed for that setting.

**[7] `nqr`**
National Qualification Register, Government of India. [Online]. Available: https://nqr.gov.in/ (accessed Oct. 28, 2026).
- Verified: https://nqr.gov.in/nsqf (page title "National Qualification Register"; site description: "the official national public record of all qualifications aligned to NSQF levels").
- Relevance: The NQR is the authoritative source of NSQF-aligned qualifications/job roles that form the target label set for Hunar's M1 mapper.

**[8] `uil2012rva`**
UNESCO Institute for Lifelong Learning, *UNESCO Guidelines for the Recognition, Validation and Accreditation of the Outcomes of Non-formal and Informal Learning*. Hamburg, Germany: UIL, 2012. Doc. UIL/2012/PI/H/3 REV.2.
- URL: https://unesdoc.unesco.org/ark:/48223/pf0000216360
- Verified: https://unesdoc.unesco.org/ark:/48223/pf0000216360 (catalogue record gives the title, UIL as publisher, Hamburg, 2012, 13 pp., document code).
- Relevance: These are the international reference principles for validating non-formal and informal learning, which is what Hunar operationalises.

**[9] `aggarwal2015rpl`**
A. Aggarwal, *Recognition of Prior Learning: Key Success Factors and the Building Blocks of an Effective System*. Pretoria, South Africa: International Labour Organization, 2015. ISBN 978-92-2-129617-1 (web pdf).
- URL: https://www.ilo.org/publications/recognition-prior-learning-key-success-factors-and-building-blocks
- Verified: the ILO publication page above and its PDF (https://www.ilo.org/sites/default/files/wcmsp5/groups/public/%40ed_emp/%40ifp_skills/documents/publication/wcms_625895.pdf). The cover and cataloguing data were read: author Ashwani Aggarwal; "Pretoria: ILO, 2015"; ISBN 9789221296164 (print), 9789221296171 (web pdf).
- Relevance: This is the ILO's analysis of what makes RPL systems work, including assessment quality and credibility, which motivates Hunar's rubric and audit design. (The brief attributed this title to "Braňka 2018"; see the UNVERIFIED section.)

**[10] `ilo2018rpl`**
International Labour Office, Skills and Employability Branch, *Recognition of Prior Learning (RPL): Learning Package*. Geneva, Switzerland: ILO, 2018. ISBN 978-92-2-131593-3 (web pdf).
- URL: https://www.ilo.org/wcmsp5/groups/public/---ed_emp/---ifp_skills/documents/publication/wcms_626246.pdf
- Verified: the PDF at the URL above was downloaded and the copyright/cataloguing page read ("Geneva: ILO, 2018"; ISBN 978-92-2-131593-3).
- Relevance: This is the ILO training package on how to build RPL systems, covering assessment methods, stakeholder roles and quality assurance. Hunar's assessor-in-the-loop design follows these building blocks.

**[11] `mospi2026plfs`**
National Statistics Office, Ministry of Statistics and Programme Implementation, Government of India, *Annual Report, Periodic Labour Force Survey (PLFS), January–December 2025*, Mar. 2026. [Online]. Available: https://www.mospi.gov.in/uploads/publications_reports/publications_reports1780040415321_0624fb13-fb47-40bc-b470-7c7e9635c3ef_PLFS_2025_F_REV_29052026.pdf
- Verified: the PDF at the URL above was downloaded and read (cover: "Annual Report, Periodic Labour Force Survey (PLFS) (January – December 2025)", NSO, MoSPI, March 2026).
- **Figures quoted from this source.** All are all-India, rural+urban, persons, PLFS 2025:
  - Statement 9 (printed p. 20, PDF p. 50). The report treats "proprietary and partnership enterprises" as informal sector enterprises. **73.1%** of usual-status (ps+ss) workers in the non-agriculture sector work in such enterprises.
  - Statement 10 (printed p. 21, PDF p. 51). Among regular wage/salaried employees (ps+ss) in the non-agriculture sector, **58.2%** had no written job contract, **47.3%** were not eligible for paid leave, and **51.7%** were not eligible for any specified social security benefit.
- Relevance: This is the official Indian statistical source on how large the informal workforce is. These are the workers whose skills go uncertified and whom Hunar targets.

**[12] `ihd2024ier`**
Institute for Human Development and International Labour Organization, *India Employment Report 2024: Youth Employment, Education and Skills*, 2024. [Online]. Available: https://www.ilo.org/publications/india-employment-report-2024-youth-employment-education-and-skills
- Verified: the ILO publication page above (title; publication date 29 March 2024; PDF at https://www.ilo.org/sites/default/files/2024-08/India%20Employment%20-%20web_8%20April.pdf). The foreword, seen in search-indexed text of that PDF, says the report is the third in the IHD series and was undertaken in partnership with the ILO. No figures from this report are quoted here.
- Relevance: It is a secondary, non-government analysis of youth employment, informality and skills in India and can supplement the PLFS figures.

---

## 2. Sentence embeddings

**[13] `reimers2019sbert`**
N. Reimers and I. Gurevych, "Sentence-BERT: Sentence embeddings using Siamese BERT-networks," in *Proc. 2019 Conf. Empirical Methods in Natural Language Processing and 9th Int. Joint Conf. Natural Language Processing (EMNLP-IJCNLP)*, 2019, pp. 3980–3990, doi: 10.18653/v1/D19-1410.
- DOI: https://doi.org/10.18653/v1/D19-1410
- Verified: https://api.crossref.org/works/10.18653/v1/D19-1410
- Relevance: This is the bi-encoder architecture behind Hunar's M1 semantic mapper from worker declarations to qualification packs.

**[14] `reimers2020multilingual`**
N. Reimers and I. Gurevych, "Making monolingual sentence embeddings multilingual using knowledge distillation," in *Proc. 2020 Conf. Empirical Methods in Natural Language Processing (EMNLP)*, 2020, pp. 4512–4525, doi: 10.18653/v1/2020.emnlp-main.365.
- DOI: https://doi.org/10.18653/v1/2020.emnlp-main.365
- Verified: https://api.crossref.org/works/10.18653/v1/2020.emnlp-main.365
- Relevance: This is the distillation method behind the multilingual sentence-transformer models Hunar uses to embed English, Hindi and Hinglish text in one shared space.

**[15] `feng2022labse`**
F. Feng, Y. Yang, D. Cer, N. Arivazhagan, and W. Wang, "Language-agnostic BERT sentence embedding," in *Proc. 60th Annu. Meeting Assoc. Computational Linguistics (Vol. 1: Long Papers)*, 2022, pp. 878–891, doi: 10.18653/v1/2022.acl-long.62.
- DOI: https://doi.org/10.18653/v1/2022.acl-long.62
- Verified: https://api.crossref.org/works/10.18653/v1/2022.acl-long.62
- Relevance: LaBSE is an alternative multilingual encoder, including for Hindi, that can be compared with the M1 mapper.

**[16] `wang2020minilm`**
W. Wang, F. Wei, L. Dong, H. Bao, N. Yang, and M. Zhou, "MiniLM: Deep self-attention distillation for task-agnostic compression of pre-trained transformers," in *Advances in Neural Information Processing Systems*, vol. 33, 2020, pp. 5776–5788.
- URL: https://proceedings.neurips.cc/paper/2020/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html
- Verified: the NeurIPS proceedings page above (citation metadata: vol. 33, pp. 5776–5788) and arXiv:2002.10957 (http://export.arxiv.org/api/query?id_list=2002.10957).
- Relevance: MiniLM is the compact transformer family behind the small multilingual embedding models that let Hunar run on low-cost hardware.

**[17] `devlin2019bert`**
J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, "BERT: Pre-training of deep bidirectional transformers for language understanding," in *Proc. 2019 Conf. North American Chapter Assoc. Computational Linguistics: Human Language Technologies, Vol. 1 (Long and Short Papers)*, 2019, pp. 4171–4186, doi: 10.18653/v1/N19-1423.
- DOI: https://doi.org/10.18653/v1/N19-1423
- Verified: https://api.crossref.org/works/10.18653/v1/N19-1423
- Relevance: BERT is the pre-trained transformer that all the sentence encoders above build on.

---

## 3. Skill extraction and occupation/skill taxonomy matching

**[18] `levrang2014esco`**
M. le Vrang, A. Papantoniou, E. Pauwels, P. Fannes, D. Vandensteen, and J. De Smedt, "ESCO: Boosting job matching in Europe with semantic interoperability," *Computer*, vol. 47, no. 10, pp. 57–64, Oct. 2014, doi: 10.1109/MC.2014.283.
- DOI: https://doi.org/10.1109/MC.2014.283
- Verified: https://api.crossref.org/works/10.1109/MC.2014.283. The live ESCO portal was also checked at https://esco.ec.europa.eu/en/about-esco/what-esco ("the European multilingual classification of Skills, Competences and Occupations").
- Relevance: ESCO is the best-known multilingual occupation/skill taxonomy and is the international counterpart of the NSQF qualification packs Hunar maps to.

**[19] `zhang2022skillspan`**
M. Zhang, K. Jensen, S. Sonniks, and B. Plank, "SkillSpan: Hard and soft skill extraction from English job postings," in *Proc. 2022 Conf. North American Chapter Assoc. Computational Linguistics: Human Language Technologies*, 2022, pp. 4962–4984, doi: 10.18653/v1/2022.naacl-main.366.
- DOI: https://doi.org/10.18653/v1/2022.naacl-main.366
- Verified: https://api.crossref.org/works/10.18653/v1/2022.naacl-main.366 and https://aclanthology.org/2022.naacl-main.366/
- Relevance: It provides a benchmark and method for extracting skill spans from free text, the problem Hunar faces with self-declarations.

**[20] `decorte2021jobbert`**
J.-J. Decorte, J. Van Hautte, T. Demeester, and C. Develder, "JobBERT: Understanding job titles through skills," arXiv:2109.09605, 2021. (Accepted to the FEAST workshop at ECML-PKDD 2021, per the arXiv comment.)
- URL: https://arxiv.org/abs/2109.09605
- Verified: http://export.arxiv.org/api/query?id_list=2109.09605
- Relevance: It shows that job-title embeddings improve when supervised with skill information, which supports skill-aware representations for occupation matching in M1.

**[21] `senger2024survey`**
E. Senger, M. Zhang, R. van der Goot, and B. Plank, "Deep learning-based computational job market analysis: A survey on skill extraction and classification from job postings," in *Proc. First Workshop on Natural Language Processing for Human Resources (NLP4HR 2024)*, 2024, pp. 1–15, doi: 10.18653/v1/2024.nlp4hr-1.1.
- DOI: https://doi.org/10.18653/v1/2024.nlp4hr-1.1
- Verified: https://aclanthology.org/2024.nlp4hr-1.1/
- Relevance: This survey of skill extraction and classification places Hunar's declaration-to-qualification mapping within that field.

**[22] `zhang2023escoxlmr`**
M. Zhang, R. van der Goot, and B. Plank, "ESCOXLM-R: Multilingual taxonomy-driven pre-training for the job market domain," in *Proc. 61st Annu. Meeting Assoc. Computational Linguistics (Vol. 1: Long Papers)*, 2023, pp. 11871–11890, doi: 10.18653/v1/2023.acl-long.662.
- DOI: https://doi.org/10.18653/v1/2023.acl-long.662
- Verified: https://api.crossref.org/works/10.18653/v1/2023.acl-long.662 and https://aclanthology.org/2023.acl-long.662/
- Relevance: It uses a multilingual occupation/skill taxonomy (ESCO) to pre-train encoders, which is directly comparable to Hunar's use of NSQF qualification packs as the label space.

---

## 4. Retrieval baselines and metrics

**[23] `salton1988tfidf`**
G. Salton and C. Buckley, "Term-weighting approaches in automatic text retrieval," *Information Processing & Management*, vol. 24, no. 5, pp. 513–523, 1988, doi: 10.1016/0306-4573(88)90021-0.
- DOI: https://doi.org/10.1016/0306-4573(88)90021-0
- Verified: https://api.crossref.org/works/10.1016/0306-4573(88)90021-0
- Relevance: This is the standard reference for TF-IDF weighting, used for Hunar's TF-IDF baseline in M1.

**[24] `robertson2009bm25`**
S. Robertson and H. Zaragoza, "The probabilistic relevance framework: BM25 and beyond," *Foundations and Trends in Information Retrieval*, vol. 3, pp. 333–389, 2009, doi: 10.1561/1500000019.
- DOI: https://doi.org/10.1561/1500000019
- Verified: https://api.semanticscholar.org/graph/v1/paper/DOI:10.1561/1500000019 (vol. 3, pp. 333–389; DBLP id journals/ftir/RobertsonZ09). **Note:** the publisher's current Crossref record (https://api.crossref.org/works/10.1561/1500000019, hosted by Emerald) lists vol. 4, nos. 1–2, pp. 1–174. The commonly cited vol. 3 pagination is used here; check this against your department's style.
- Relevance: BM25 is the standard lexical-retrieval baseline that a keyword baseline can be strengthened with.

**[25] `voorhees1999trec8qa`**
E. M. Voorhees, "The TREC-8 question answering track report," in *The Eighth Text REtrieval Conference (TREC-8)*, NIST Special Publication 500-246, 1999, pp. 77–82.
- URL: https://trec.nist.gov/pubs/trec8/papers/qa_report.pdf
- Verified: https://trec.nist.gov/pubs/trec8/t8_proceedings.html (table of contents: SP 500-246, "The TREC-8 Question Answering Track Report", E. Voorhees, page 77; the PDF has 6 pages). The PDF text was read: each question is scored by the reciprocal of the rank of the first correct response, and a run's score is the mean over questions.
- Relevance: This is the original definition of mean reciprocal rank (MRR), one of M1's per-language evaluation metrics.

---

## 5. Code-mixed Hindi–English (Hinglish) NLP

**[26] `khanuja2020gluecos`**
S. Khanuja, S. Dandapat, A. Srinivasan, S. Sitaram, and M. Choudhury, "GLUECoS: An evaluation benchmark for code-switched NLP," in *Proc. 58th Annu. Meeting Assoc. Computational Linguistics*, 2020, pp. 3575–3585, doi: 10.18653/v1/2020.acl-main.329.
- DOI: https://doi.org/10.18653/v1/2020.acl-main.329
- Verified: https://api.crossref.org/works/10.18653/v1/2020.acl-main.329 and https://aclanthology.org/2020.acl-main.329/
- Relevance: This is a standard benchmark of code-switched NLP tasks, including Hindi–English, and supports reporting Hinglish results separately from English and Hindi.

**[27] `bali2014codemixing`**
K. Bali, J. Sharma, M. Choudhury, and Y. Vyas, "'I am borrowing ya mixing?' An analysis of English-Hindi code mixing in Facebook," in *Proc. First Workshop on Computational Approaches to Code Switching*, 2014, pp. 116–126, doi: 10.3115/v1/W14-3914.
- DOI: https://doi.org/10.3115/v1/W14-3914
- Verified: https://api.crossref.org/works/10.3115/v1/W14-3914 and https://aclanthology.org/W14-3914/
- Relevance: This is an early empirical study of how English–Hindi code-mixing occurs in user-generated text, the register of Hunar's Hinglish declarations.

**[28] `dogruoz2021survey`**
A. S. Doğruöz, S. Sitaram, B. E. Bullock, and A. J. Toribio, "A survey of code-switching: Linguistic and social perspectives for language technologies," in *Proc. 59th Annu. Meeting Assoc. Computational Linguistics and 11th Int. Joint Conf. Natural Language Processing (Vol. 1: Long Papers)*, 2021, pp. 1654–1666, doi: 10.18653/v1/2021.acl-long.131.
- DOI: https://doi.org/10.18653/v1/2021.acl-long.131
- Verified: https://api.crossref.org/works/10.18653/v1/2021.acl-long.131 and https://aclanthology.org/2021.acl-long.131/
- Relevance: This survey supports the linguistic framing of Hinglish input in the report.

---

## 6. Object detection and PPE detection

**[29] `redmon2016yolo`**
J. Redmon, S. Divvala, R. Girshick, and A. Farhadi, "You only look once: Unified, real-time object detection," in *Proc. IEEE Conf. Computer Vision and Pattern Recognition (CVPR)*, 2016, pp. 779–788, doi: 10.1109/CVPR.2016.91.
- DOI: https://doi.org/10.1109/CVPR.2016.91
- Verified: https://api.crossref.org/works/10.1109/CVPR.2016.91
- Relevance: This is the original single-stage YOLO detector, the ancestor of the YOLOv8-nano model in M2.

**[30] `jocher2023yolov8`**
G. Jocher, A. Chaurasia, and J. Qiu, "Ultralytics YOLOv8," version 8.0.0, 2023. [Online]. Available: https://github.com/ultralytics/ultralytics (AGPL-3.0 license).
- Verified: https://docs.ultralytics.com/models/yolov8/ (official citation block: authors, title, version 8.0.0, year 2023, URL, AGPL-3.0; the page says no formal YOLOv8 paper exists). Also https://raw.githubusercontent.com/ultralytics/ultralytics/main/CITATION.cff (date-released 2023-01-10).
- Relevance: This is the software used for M2's PPE/tool presence detector. Its AGPL-3.0 licence should be noted in the report.

**[31] `lin2014coco`**
T.-Y. Lin, M. Maire, S. Belongie, J. Hays, P. Perona, D. Ramanan, P. Dollár, and C. L. Zitnick, "Microsoft COCO: Common objects in context," in *Computer Vision – ECCV 2014* (Lecture Notes in Computer Science). Springer International Publishing, 2014, pp. 740–755, doi: 10.1007/978-3-319-10602-1_48.
- DOI: https://doi.org/10.1007/978-3-319-10602-1_48
- Verified: https://api.crossref.org/works/10.1007/978-3-319-10602-1_48
- Relevance: COCO provides the pre-training data for YOLOv8 checkpoints and the standard mAP evaluation protocol used to report M2.

**[32] `nath2020ppe`**
N. D. Nath, A. H. Behzadan, and S. G. Paal, "Deep learning for site safety: Real-time detection of personal protective equipment," *Automation in Construction*, vol. 112, Art. no. 103085, Apr. 2020, doi: 10.1016/j.autcon.2020.103085.
- DOI: https://doi.org/10.1016/j.autcon.2020.103085
- Verified: https://api.crossref.org/works/10.1016/j.autcon.2020.103085
- Relevance: This is prior work on YOLO-based real-time PPE detection, the same task as M2's PPE-presence check on task photos.

**[33] `fang2018hardhat`**
Q. Fang, H. Li, X. Luo, L. Ding, H. Luo, T. M. Rose, and W. An, "Detecting non-hardhat-use by a deep learning method from far-field surveillance videos," *Automation in Construction*, vol. 85, pp. 1–9, Jan. 2018, doi: 10.1016/j.autcon.2017.09.018.
- DOI: https://doi.org/10.1016/j.autcon.2017.09.018
- Verified: https://api.crossref.org/works/10.1016/j.autcon.2017.09.018
- Relevance: This is early deep-learning hardhat detection on construction sites and a baseline reference for M2.

**[34] `wang2021chv`**
Z. Wang, Y. Wu, L. Yang, A. Thirunavukarasu, C. Evison, and Y. Zhao, "Fast personal protective equipment detection for real construction sites using deep learning approaches," *Sensors*, vol. 21, no. 10, Art. no. 3478, 2021, doi: 10.3390/s21103478.
- DOI: https://doi.org/10.3390/s21103478
- Verified: https://api.crossref.org/works/10.3390/s21103478 (metadata and abstract)
- Relevance: The paper releases the public CHV PPE dataset (1,330 images: helmets, vest, person), which M2 can use. Its abstract also reports that helmet detection accuracy drops by 7% on blurred faces, which bears directly on Hunar's blur-faces-before-storage design.

---

## 7. Perceptual hashing and near-duplicate image detection

**[35] `zauner2010phash`**
C. Zauner, "Implementation and benchmarking of perceptual image hash functions," M.S. thesis, Upper Austria Univ. of Applied Sciences, Hagenberg Campus, Austria, 2010.
- URL: https://www.phash.org/docs/pubs/thesis_zauner.pdf
- Verified: https://www.phash.org/docs/ (lists "Zauner, Christoph: Implementation and Benchmarking of Perceptual Image Hash Functions. Master's thesis, Upper Austria University of Applied Sciences, Hagenberg Campus, 2010"). The PDF URL above returns the thesis (HTTP 200, application/pdf).
- Relevance: This thesis benchmarks DCT-based pHash and related functions and justifies M2's use of pHash for detecting reused evidence photos.

**[36] `monga2006hashing`**
V. Monga and B. L. Evans, "Perceptual image hashing via feature points: Performance evaluation and tradeoffs," *IEEE Trans. Image Processing*, vol. 15, no. 11, pp. 3452–3465, Nov. 2006, doi: 10.1109/TIP.2006.881948.
- DOI: https://doi.org/10.1109/TIP.2006.881948
- Verified: https://api.crossref.org/works/10.1109/TIP.2006.881948
- Relevance: It covers the robustness/discrimination trade-off in perceptual hashing, which informs how M2 picks its Hamming-distance threshold.

**[37] `venkatesan2000robust`**
R. Venkatesan, S.-M. Koon, M. H. Jakubowski, and P. Moulin, "Robust image hashing," in *Proc. 2000 Int. Conf. Image Processing (ICIP)*, 2000, pp. 664–666, doi: 10.1109/ICIP.2000.899541.
- DOI: https://doi.org/10.1109/ICIP.2000.899541
- Verified: https://api.crossref.org/works/10.1109/ICIP.2000.899541 (volume number not given by Crossref, so omitted)
- Relevance: This is a foundational paper on image hashes that stay stable under benign changes such as compression and resizing, the property M2 relies on.

**[38] `farid2021perceptual`**
H. Farid, "An overview of perceptual hashing," *Journal of Online Trust and Safety*, vol. 1, no. 1, Oct. 2021, doi: 10.54501/jots.v1i1.24.
- DOI: https://doi.org/10.54501/jots.v1i1.24
- Verified: https://api.crossref.org/works/10.54501/jots.v1i1.24
- Relevance: This is an accessible recent overview of perceptual hashing for content matching, including its limits and adversarial weaknesses, to cite in the M2 threat-model discussion.

**[39] `buchner2025imagehash`**
J. Buchner, "ImageHash: Image hashing library" (Python package), version 4.3.2, 2025. [Online]. Available: https://github.com/JohannesBuchner/imagehash
- Verified: https://pypi.org/pypi/ImageHash/json (name ImageHash, version 4.3.2 uploaded 2025-02-01, author Johannes Buchner, summary "Image Hashing library", 2-clause BSD licence, homepage as above).
- Relevance: This is the library M2 uses to compute pHash/dHash fingerprints. Pin the version you actually installed.

---

## 8. Inter-rater reliability and resampling statistics

**[40] `cohen1960kappa`**
J. Cohen, "A coefficient of agreement for nominal scales," *Educational and Psychological Measurement*, vol. 20, no. 1, pp. 37–46, 1960, doi: 10.1177/001316446002000104.
- DOI: https://doi.org/10.1177/001316446002000104
- Verified: https://api.crossref.org/works/10.1177/001316446002000104
- Relevance: This defines chance-corrected agreement (kappa), the basis of M4's reliability analysis.

**[41] `fleiss1971kappa`**
J. L. Fleiss, "Measuring nominal scale agreement among many raters," *Psychological Bulletin*, vol. 76, no. 5, pp. 378–382, 1971, doi: 10.1037/h0031619.
- DOI: https://doi.org/10.1037/h0031619
- Verified: https://api.crossref.org/works/10.1037/h0031619
- Relevance: This defines Fleiss' kappa for more than two raters, used in M4 to compare unassisted and rubric-assisted assessors.

**[42] `landis1977agreement`**
J. R. Landis and G. G. Koch, "The measurement of observer agreement for categorical data," *Biometrics*, vol. 33, no. 1, pp. 159–174, 1977, doi: 10.2307/2529310.
- DOI: https://doi.org/10.2307/2529310
- Verified: https://api.crossref.org/works/10.2307/2529310 and https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=843571&retmode=json (PubMed: Biometrics 1977 Mar;33(1):159-74)
- Relevance: This is the source of the widely used verbal benchmarks ("slight", "fair", "moderate", ...) for interpreting kappa values in M4.

**[43] `krippendorff2004content`**
K. Krippendorff, *Content Analysis: An Introduction to Its Methodology*, 2nd ed. Thousand Oaks, CA, USA: Sage, 2004.
- Verified: https://openlibrary.org/isbn/0761915451 (2nd ed., Sage, Thousand Oaks, Calif., 2004; ISBN 0-7619-1544-3 / 0-7619-1545-1; "by Klaus Krippendorff")
- Relevance: This is the methodological source for Krippendorff's alpha, including its ordinal variant used for M4's 0–3 rubric scores.

**[44] `hayes2007alpha`**
A. F. Hayes and K. Krippendorff, "Answering the call for a standard reliability measure for coding data," *Communication Methods and Measures*, vol. 1, no. 1, pp. 77–89, 2007, doi: 10.1080/19312450709336664.
- DOI: https://doi.org/10.1080/19312450709336664
- Verified: https://api.crossref.org/works/10.1080/19312450709336664
- Relevance: It argues for Krippendorff's alpha as the standard reliability measure for coded data, which justifies reporting alpha alongside Fleiss' kappa in M4.

**[45] `hallgren2012irr`**
K. A. Hallgren, "Computing inter-rater reliability for observational data: An overview and tutorial," *Tutorials in Quantitative Methods for Psychology*, vol. 8, no. 1, pp. 23–34, 2012, doi: 10.20982/tqmp.08.1.p023.
- DOI: https://doi.org/10.20982/tqmp.08.1.p023
- Verified: https://api.crossref.org/works/10.20982/tqmp.08.1.p023
- Relevance: This practical tutorial on choosing and reporting IRR statistics guides how M4 results are presented.

**[46] `efron1993bootstrap`**
B. Efron and R. J. Tibshirani, *An Introduction to the Bootstrap* (Monographs on Statistics and Applied Probability, no. 57). New York, NY, USA: Chapman & Hall, 1993, doi: 10.1007/978-1-4899-4541-9.
- DOI: https://doi.org/10.1007/978-1-4899-4541-9
- Verified: https://api.crossref.org/works/10.1007/978-1-4899-4541-9 (book, 1993, ISBN 9780412042317) and https://openlibrary.org/isbn/0412042312 (Chapman & Hall, New York, 1993; series no. 57)
- Relevance: This is the standard reference for the bootstrap confidence intervals placed around M4's kappa/alpha estimates.

---

## 9. Rubrics, anchored scales and assessor consistency

**[47] `jonsson2007rubrics`**
A. Jonsson and G. Svingby, "The use of scoring rubrics: Reliability, validity and educational consequences," *Educational Research Review*, vol. 2, no. 2, pp. 130–144, 2007, doi: 10.1016/j.edurev.2007.05.002.
- DOI: https://doi.org/10.1016/j.edurev.2007.05.002
- Verified: https://api.crossref.org/works/10.1016/j.edurev.2007.05.002
- Relevance: This review of evidence that analytic rubrics can improve scoring reliability motivates M3's anchored 0–3 rubric and M4's hypothesis.

**[48] `smith1963bars`**
P. C. Smith and L. M. Kendall, "Retranslation of expectations: An approach to the construction of unambiguous anchors for rating scales," *Journal of Applied Psychology*, vol. 47, no. 2, pp. 149–155, 1963, doi: 10.1037/h0047060.
- DOI: https://doi.org/10.1037/h0047060
- Verified: https://api.crossref.org/works/10.1037/h0047060
- Relevance: This is the classic method for building behaviourally anchored rating scales, the basis for writing M3's per-level anchors.

**[49] `roch2012fortraining`**
S. G. Roch, D. J. Woehr, V. Mishra, and U. Kieszczynska, "Rater training revisited: An updated meta-analytic review of frame-of-reference training," *Journal of Occupational and Organizational Psychology*, vol. 85, no. 2, pp. 370–395, 2012, doi: 10.1111/j.2044-8325.2011.02045.x.
- DOI: https://doi.org/10.1111/j.2044-8325.2011.02045.x
- Verified: https://api.crossref.org/works/10.1111/j.2044-8325.2011.02045.x
- Relevance: This meta-analysis of frame-of-reference rater training gives the evidence base for calibrating assessors with shared anchors and examples, as M3 does.

**[50] `johnson2008assessor`**
M. Johnson, "Exploring assessor consistency in a Health and Social Care qualification using a sociocultural perspective," *Journal of Vocational Education & Training*, vol. 60, no. 2, pp. 173–187, 2008, doi: 10.1080/13636820802042446.
- DOI: https://doi.org/10.1080/13636820802042446
- Verified: https://api.crossref.org/works/10.1080/13636820802042446
- Relevance: It studies assessor consistency specifically in vocational qualification assessment, the setting of Hunar's M4 study.

---

## 10. Human–AI decision support and automation bias

**[51] `amershi2019guidelines`**
S. Amershi, D. Weld, M. Vorvoreanu, A. Fourney, B. Nushi, P. Collisson, J. Suh, S. Iqbal, P. N. Bennett, K. Inkpen, J. Teevan, R. Kikin-Gil, and E. Horvitz, "Guidelines for human-AI interaction," in *Proc. 2019 CHI Conf. Human Factors in Computing Systems*, 2019, pp. 1–13, doi: 10.1145/3290605.3300233.
- DOI: https://doi.org/10.1145/3290605.3300233
- Verified: https://api.crossref.org/works/10.1145/3290605.3300233
- Relevance: These are design guidelines, such as making clear what the system can do and supporting efficient correction, that shape Hunar's "AI suggests, assessor decides" interface and override flow.

**[52] `parasuraman2010complacency`**
R. Parasuraman and D. H. Manzey, "Complacency and bias in human use of automation: An attentional integration," *Human Factors*, vol. 52, no. 3, pp. 381–410, 2010, doi: 10.1177/0018720810376055.
- DOI: https://doi.org/10.1177/0018720810376055
- Verified: https://api.crossref.org/works/10.1177/0018720810376055
- Relevance: This defines automation bias and complacency, the main risk of showing AI pre-scores to assessors, which M4 should measure as anchoring.

**[53] `doshivelez2017interpretable`**
F. Doshi-Velez and B. Kim, "Towards a rigorous science of interpretable machine learning," arXiv:1702.08608, 2017.
- URL: https://arxiv.org/abs/1702.08608
- Verified: http://export.arxiv.org/api/query?id_list=1702.08608
- Relevance: It offers a framework for evaluating interpretability and supports M3's explainable pre-scores (showing which evidence triggered each rubric level).

---

## 11. Tamper-evident audit logs

**[54] `schneier1999auditlogs`**
B. Schneier and J. Kelsey, "Secure audit logs to support computer forensics," *ACM Trans. Information and System Security*, vol. 2, no. 2, pp. 159–176, May 1999, doi: 10.1145/317087.317089.
- DOI: https://doi.org/10.1145/317087.317089
- Verified: https://api.crossref.org/works/10.1145/317087.317089
- Relevance: This is the classic hash-chained, forward-secure audit log design that M3's append-only hash-chained log follows.

**[55] `crosby2009tamper`**
S. A. Crosby and D. S. Wallach, "Efficient data structures for tamper-evident logging," in *Proc. 18th USENIX Security Symp. (USENIX Security '09)*, Montreal, QC, Canada, Aug. 2009.
- URL: https://www.usenix.org/conference/usenixsecurity09/technical-sessions/presentation/efficient-data-structures-tamper-evident
- Verified: the USENIX page above (authors Scott A. Crosby and Dan S. Wallach, Rice University; USENIX BibTeX: booktitle "18th USENIX Security Symposium (USENIX Security 09)", 2009, Montreal, Quebec, month Aug). Page numbers were not shown, so they are omitted.
- Relevance: It proposes a Merkle-tree tamper-evident log with logarithmic-size proofs, the natural upgrade path from M3's linear hash chain.

---

## 12. Offline-first / local-first software

**[56] `kleppmann2019localfirst`**
M. Kleppmann, A. Wiggins, P. van Hardenberg, and M. McGranaghan, "Local-first software: You own your data, in spite of the cloud," in *Proc. 2019 ACM SIGPLAN Int. Symp. New Ideas, New Paradigms, and Reflections on Programming and Software (Onward! '19)*, 2019, pp. 154–178, doi: 10.1145/3359591.3359737.
- DOI: https://doi.org/10.1145/3359591.3359737
- Verified: https://api.crossref.org/works/10.1145/3359591.3359737
- Relevance: These are design principles for apps that keep working offline and sync later, the basis for M5's IndexedDB sync-queue PWA used in low-connectivity assessment centres.

---

## 13. Speech

**[57] `radford2023whisper`**
A. Radford, J. W. Kim, T. Xu, G. Brockman, C. McLeavey, and I. Sutskever, "Robust speech recognition via large-scale weak supervision," in *Proc. Int. Conf. Machine Learning (ICML)*, ser. Proceedings of Machine Learning Research, vol. 202, 2023, pp. 28492–28518.
- URL: https://proceedings.mlr.press/v202/radford23a.html
- Verified: https://proceedings.mlr.press/v202/radford23a.html (citation metadata: pp. 28492–28518, 2023, PMLR) and arXiv:2212.04356
- Relevance: Whisper is the multilingual speech-recognition model for letting workers dictate self-declarations in Hindi or Hinglish instead of typing them.

---

## 14. Privacy: face detection and blurring

**[58] `viola2001rapid`**
P. Viola and M. Jones, "Rapid object detection using a boosted cascade of simple features," in *Proc. 2001 IEEE Computer Society Conf. Computer Vision and Pattern Recognition (CVPR)*, vol. 1, 2001, pp. I-511–I-518, doi: 10.1109/CVPR.2001.990517.
- DOI: https://doi.org/10.1109/CVPR.2001.990517
- Verified: https://api.crossref.org/works/10.1109/CVPR.2001.990517
- Relevance: This is the cascade face detector (as shipped with OpenCV Haar cascades) that can locate faces to blur before evidence photos are stored.

**[59] `frome2009streetview`**
A. Frome, G. Cheung, A. Abdulkader, M. Zennaro, B. Wu, A. Bissacco, H. Adam, H. Neven, and L. Vincent, "Large-scale privacy protection in Google Street View," in *Proc. IEEE 12th Int. Conf. Computer Vision (ICCV)*, 2009, pp. 2373–2380, doi: 10.1109/ICCV.2009.5459413.
- DOI: https://doi.org/10.1109/ICCV.2009.5459413
- Verified: https://api.crossref.org/works/10.1109/ICCV.2009.5459413
- Relevance: This is a precedent for automated detect-and-blur of faces at scale, the privacy-by-design step Hunar applies before storage.

---

## 15. Technology and RPL / skill certification (including India)

**[60] `rothboeck2018rpl`**
S. Rothboeck, P. Comyn, and P. S. Banerjee, "Role of recognition of prior learning for emerging economies: Learning from a four sector pilot project in India," *Journal of Education and Work*, vol. 31, no. 4, pp. 394–408, 2018, doi: 10.1080/13639080.2018.1473560.
- DOI: https://doi.org/10.1080/13639080.2018.1473560
- Verified: https://api.crossref.org/works/10.1080/13639080.2018.1473560
- Relevance: This is a peer-reviewed study of RPL piloted across four sectors in India and gives empirical context for the problem Hunar addresses.

**[61] `singh2019rpl`**
S. Singh and S. Ehlers, "Recognition of prior learning: Policy analysis from Denmark and India," *Andragoška spoznanja / Studies in Adult Education and Learning*, vol. 25, no. 1, pp. 69–87, 2019, doi: 10.4312/as.25.1.69-87.
- DOI: https://doi.org/10.4312/as.25.1.69-87
- Verified: https://api.crossref.org/works/10.4312/as.25.1.69-87 and the DOI landing page (citation_title "Recognition of Prior Learning: Policy analysis from Denmark and India")
- Relevance: This is a comparative policy analysis of India's RPL system that helps frame Hunar within national skills policy.

**[62] `rambharose2025airpl`**
R. Rambharose, "Exploring the role of artificial intelligence (AI) in recognition of prior learning: Opportunities for transforming adult learning and assessment," *Journal of Vocational, Adult and Continuing Education and Training*, vol. 8, no. 1, 2025, doi: 10.14426/jovacet.v8i1.506.
- DOI: https://doi.org/10.14426/jovacet.v8i1.506
- Verified: https://api.crossref.org/works/10.14426/jovacet.v8i1.506 and the DOI landing page (journal, vol. 8, no. 1, dated 2025-10-17). Page range unclear in the metadata, so omitted.
- Relevance: This is recent peer-reviewed work on AI in RPL assessment and the closest academic precedent for an AI-assisted RPL tool such as Hunar.

## 16. Data splitting

**[63] `sechidis2011stratification`**
K. Sechidis, G. Tsoumakas, and I. Vlahavas, "On the stratification of multi-label data," in *Machine Learning and Knowledge Discovery in Databases (ECML PKDD 2011)* (Lecture Notes in Computer Science), 2011, pp. 145–158, doi: 10.1007/978-3-642-23808-6_10.
- DOI: https://doi.org/10.1007/978-3-642-23808-6_10
- Verified: https://api.crossref.org/works?query.bibliographic=On+the+stratification+of+multi-label+data (Crossref record: title, authors Sechidis/Tsoumakas/Vlahavas, LNCS, pp. 145–158, 2011), checked 3 Nov 2026.
- Relevance: Iterative stratification, which Hunar adapts to groups of near-identical video frames to re-split the PPE dataset so every class appears in every split.

## 17. Speech recognition software

**[64] `systran_fasterwhisper`**
SYSTRAN, "faster-whisper: Faster Whisper transcription with CTranslate2," version 1.2.1, software, GitHub repository. [Online]. Available: https://github.com/SYSTRAN/faster-whisper (MIT license).
- Verified: https://github.com/SYSTRAN/faster-whisper (owner SYSTRAN, MIT license, "a reimplementation of OpenAI's Whisper model using CTranslate2"; the repository gives no formal citation), checked 3 Nov 2026. Version from the installed package metadata.
- Relevance: The speech-recognition library behind Hunar's optional spoken declarations (Whisper `small`, CPU, int8). The model itself is [57].

## 18. Two-sided app: law, measurement, accessibility, language technology and trade standards

**[65] `cea2023safety`**
Central Electricity Authority, "Central Electricity Authority (Measures relating to Safety and Electric Supply) Regulations, 2023," Gazette of India, notification No. CEA-PS-16/1/2021-CEI Division, 8 Jun. 2023. [Online]. Available: https://cea.nic.in/whats-new/file?path=%2Fhome%2Fcea_website%2Freports%2Fgeneral%2Fen%2Fpdf_100_183_English.pdf&mode=view
- Verified: Official CEA PDF read in full by a research agent, 3 Nov 2026 (regs 17, 18, 20, 21, 30, 31, 33-37, 42-44 and Schedule I).
- Relevance: Legal basis for permit-only electrical jobs in booking (reg. 31) and for most electrician quiz answers.

**[66] `dpdp2023`**
Government of India, "The Digital Personal Data Protection Act, 2023," enacted 11 Aug. 2023; Digital Personal Data Protection Rules, 2025, notified 14 Nov. 2025. [Online]. Available: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2190014
- Verified: Dates and themes from PIB/MeitY releases (3 Nov 2026). Section wording was read from a third-party mirror and must be checked against the official MeitY text.
- Relevance: Itemised consent, withdrawal, erasure and adults-only design of accounts.

**[67] `linacre1994sample`**
J. M. Linacre, "Sample size and item calibration [or person measure] stability," Rasch Measurement Transactions, vol. 7, no. 4, p. 328, 1994. [Online]. Available: https://www.rasch.org/rmt/rmt74m.htm
- Verified: Opened 4 Nov 2026: title, author, RMT 7:4 p. 328, 1994; table of sample sizes for +/- 1 and +/- 1/2 logit.
- Relevance: Why the quiz uses the Rasch model and needs about 100-150 answers per item before calibration.

**[68] `thompson2011cat`**
N. A. Thompson and D. J. Weiss, "A framework for the development of computerized adaptive tests," Practical Assessment, Research, and Evaluation, vol. 16, art. 1, 2011, doi: 10.7275/wqzt-9427.
- Verified: DOI checked against Crossref by a research agent, 3 Nov 2026.
- Relevance: CAT design steps, item-bank sizes, stopping rules; 3PL calibration sample sizes.

**[69] `bock1982eap`**
R. D. Bock and R. J. Mislevy, "Adaptive EAP estimation of ability in a microcomputer environment," Applied Psychological Measurement, vol. 6, no. 4, pp. 431-444, 1982, doi: 10.1177/014662168200600405.
- Verified: DOI checked against Crossref by a research agent, 3 Nov 2026.
- Relevance: EAP scoring used by the quiz engine.

**[70] `kingsbury1989cat`**
G. G. Kingsbury and A. R. Zara, "Procedures for selecting items for computerized adaptive tests," Applied Measurement in Education, vol. 2, no. 4, pp. 359-375, 1989, doi: 10.1207/s15324818ame0204_6.
- Verified: DOI checked against Crossref by a research agent, 3 Nov 2026.
- Relevance: Content balancing across NOS during item selection.

**[71] `mislevy1988aux`**
R. J. Mislevy, "Exploiting auxiliary information about items in the estimation of Rasch item difficulty parameters," Applied Psychological Measurement, vol. 12, no. 3, pp. 281-296, 1988, doi: 10.1177/014662168801200306.
- Verified: DOI checked against Crossref by a research agent, 3 Nov 2026.
- Relevance: Cold start: expert difficulty estimates as priors, refined by data.

**[72] `wise2005rte`**
S. L. Wise and X. Kong, "Response time effort: A new measure of examinee motivation in computer-based tests," Applied Measurement in Education, vol. 18, no. 2, pp. 163-183, 2005, doi: 10.1207/s15324818ame1802_2.
- Verified: DOI checked against Crossref by a research agent, 3 Nov 2026.
- Relevance: Rapid answers are flagged and not scored.

**[73] `medhi2006textfree`**
I. Medhi, A. Sagar, and K. Toyama, "Text-free user interfaces for illiterate and semi-literate users," in Proc. Int. Conf. Information and Communication Technologies and Development (ICTD), 2006, doi: 10.1109/ICTD.2006.301841.
- Verified: DOI checked against Crossref by a research agent, 3 Nov 2026.
- Relevance: Icon-led, voice-supported interface for low-literacy users.

**[74] `medhi2011mobile`**
I. Medhi, S. Patnaik, E. Brunskill, S. N. N. Gautama, W. Thies, and K. Toyama, "Designing mobile interfaces for novice and low-literacy users," ACM Transactions on Computer-Human Interaction, vol. 18, no. 1, art. 2, 2011, doi: 10.1145/1959022.1959024.
- Verified: DOI checked against Crossref by a research agent, 3 Nov 2026.
- Relevance: Text interfaces are unusable for first-time low-literacy users; graphical and spoken alternatives.

**[75] `bhashini_api`**
Digital India Bhashini Division, Ministry of Electronics and Information Technology, "Bhashini APIs: pipeline config and pipeline compute calls," online documentation. [Online]. Available: https://bhashini.gitbook.io/bhashini-apis (accessed 4 Nov. 2026).
- Verified: Opened 4 Nov 2026: config and compute request/response payloads.
- Relevance: Machine translation and text to speech for the 22 scheduled languages.

**[76] `dgt2025ctselectrician`**
Directorate General of Training (CSTARI), "Electrician, Craftsmen Training Scheme (CTS 3.0), NSQF level 4," revised Aug. 2025. [Online]. Available: https://bharatskills.gov.in/pdf/Curriculum/CTS/English/Electrician_CTS3.0_NSQF-4%20(2).pdf
- Verified: Opened by a research agent, 3 Nov 2026.
- Relevance: Topic source for electrician quiz items (Ohm's law, cables, earthing, instruments, first aid).

**[77] `wmpsc2024plumber`**
Water Management and Plumbing Skill Council, "Qualification File: Plumber - General," QG-04-PL-03441-2024-V2-WMPS, NSQF level 4, NQR id 12957, approved 17 Dec. 2024. [Online]. Available: https://www.nqr.gov.in/qualifications/12957
- Verified: PDF downloaded 4 Nov 2026; SHA-256 recorded in data/processed/qp_manifest.json.
- Relevance: Official standard behind the plumber quiz bank.

**[78] `ffsc2023carpenter`**
Furniture and Fittings Skill Council, "Qualification File: Assistant Carpenter," QG-04-WC-00828-2023-V2-FFSC, NSQF level 4, NQR id 9884 (NQR validity ended 31 Aug. 2026). [Online]. Available: https://www.nqr.gov.in/qualifications/9884
- Verified: PDF downloaded 4 Nov 2026; SHA-256 recorded in data/processed/qp_manifest.json.
- Relevance: Closest official standard behind the carpenter quiz bank (labelled as lapsed).

**[79] `bis1983is5329`**
Bureau of Indian Standards, "IS 5329:1983 Code of practice for sanitary pipe work above ground for buildings," 1983.
- Verified: Text read 4 Nov 2026 (cl. 2.23-2.24, Table 2).
- Relevance: Trap and water-seal items in the plumber bank.

**[80] `bis1983is2065`**
Bureau of Indian Standards, "IS 2065:1983 Code of practice for water supply in buildings," 1983.
- Verified: Text read 4 Nov 2026 (cl. 14.2).
- Relevance: Pressure-test item in the plumber bank.

**[81] `wang2025yoloe`**
A. Wang, L. Liu, H. Chen, Z. Lin, J. Han, and G. Ding, "YOLOE: Real-time seeing anything," arXiv:2503.07465, 2025 (ICCV 2025 camera-ready version).
- URL: https://arxiv.org/abs/2503.07465
- Verified: arXiv API record read 6 Nov 2026 (title, six authors in this order, first submitted 10 Mar 2025, v2 17 Oct 2025, comment "ICCV 2025 Camera-ready Version"). Proceedings pages not checked, so the arXiv version is cited.
- Relevance: Open-vocabulary detector prompted with a part's name and with "hand" for the video pilot's optional frame check (run through the Ultralytics library [30]).

---

## UNVERIFIED — [CITATION NEEDED]

These items are **not** in `references.bib`. Do not cite them as written.

1. **"Braňka, J. (2018). *Recognition of prior learning: key success factors and the building blocks of an effective system*. ILO."** I could not confirm this author/title/year combination. The verified sources are:
   - that exact title is by **A. Aggarwal, ILO, Pretoria, 2015** (see `aggarwal2015rpl`);
   - the ILO's **2018** RPL publication is the corporate-authored *Recognition of Prior Learning (RPL): Learning Package* (see `ilo2018rpl`), which cites "Braňka (2016a)" and "Braňka (2016b)" internally. Those 2016 Braňka works were not checked.
2. **"NITI Aayog/ILO India Employment Report 2024."** No NITI Aayog authorship was found. The ILO page and foreword credit the **Institute for Human Development** in partnership with the **ILO** (see `ihd2024ier`).
3. **Gazette of India Part/Section numbers** for the 2013 NSQF notification and the 2018 NCVET notification could not be confirmed and have been left out of [1] and [3]. Add them only after reading the gazette copy itself.
4. **Volume/issue of [24] (BM25):** sources conflict (vol. 3, pp. 333–389 per Semantic Scholar/DBLP vs. vol. 4, nos. 1–2, pp. 1–174 per the current Crossref/Emerald record). The DOI is correct either way.
