import csv
import re
from pyzotero import zotero
from django.core.management.base import BaseCommand, CommandError
from document.models import *
from past.models import *
from document.models import *
from voyage.models import *
from voyages3.settings import *
import requests
import json
import os



class Command(BaseCommand):
	'''
		This script consolidates the most obviously duplicated enslavement relations. How?
		1. run through the enslavement relations as a flat values list
		2. where we have matches on Voyage.id, EnslaverAlias.id, Enslaved.id
		2a. AND the EnslaverInRelation roles are exactly the same (there are about 50 where this isn't the case)
		3. Pick the first of those enslavement relations
		4. Connect the Enslaved to the Enslavement Relation
		5. Delete the EnslavementRelation
		That's it!
	'''
	def handle(self, *args, **options):
		
# 		print("BASIC ENSLAVERINRELATION OBJ DEDUPE: objects that point at the same alias and same relation with the same role(s)")
# 		eirs=EnslaverInRelation.objects.all()
# 		
# 		eir_dict={}
# 		
# 		eirs_vls=eirs.values_list(
# 			'relation_id',
# 			'enslaver_alias__id',
# 			'id'
# 		)
# 		
# 		for eir_vl in eirs_vls:
# 			k='__'.join([str(i) for i in (eir_vl[0],eir_vl[1])])
# 			eir_id=eir_vl[2]
# 			if k not in eir_dict:
# 				eir_dict[k]=[eir_id]
# 			else:
# 				eir_dict[k].append(eir_id)
# 		
# 		dup_count=0
# 		singles_count=0
# 		
# 		dup_keys=[]
# 		for k in eir_dict:
# 			if len(eir_dict[k])>1:
# 				dup_count+=1
# 				dup_keys.append(k)
# 			else:
# 				singles_count+=1
# 		
# 		print("duplicates:",dup_count)
# 		print("singles:",singles_count)
# 		
# 		deleted_count=0
# 		for dk in dup_keys:
# 			dk_roles=[]
# 			relation_id,enslaver_alias_id=[int(i) for i in dk.split('__')]
# 			
# 			eir_ids=eir_dict[dk]
# 			
# 			for eir_id in eir_ids:
# 				eir=EnslaverInRelation.objects.get(id=eir_id)
# 				eir_roles=[r.name for r in eir.roles.all()]
# 				eir_roles.sort()
# 				if eir_roles not in dk_roles:
# 					dk_roles.append(eir_roles)
# 				
# 			if len(dk_roles)!=1:
# 				print(dk,er_dict[dk])
# 			else:
# 				for eir_id in eir_ids[1:]:
# 					eir=EnslaverInRelation.objects.get(id=eir_id)
# 					eir.delete()
# 					deleted_count+=1
# 		print(deleted_count)
# 		
# 		exit()
		
		print("more difficult: ENSLAVEMENT RELATIONS THAT HAVE *ONE* ENSLAVER AND THE SAME VOYAGE AND THE SAME ENSLAVER_ROLE SHOULD HAVE ALL THE ENSLAVED GATHERED INTO THE SAME RELATION")
		
		enslaver_aliases=EnslaverAlias.objects.all()
# 		.filter(id=1039765)
		
		for ea in enslaver_aliases:
			relation_ids=[eir.relation.id for eir in ea.enslaver_relations.all()]
			enslaved_in_relation_dict={}
			for rel_id in relation_ids:
				relation=EnslavementRelation.objects.get(id=rel_id)
				enslaver_aliases_in_relation=list(set([eir.enslaver_alias.id for eir in relation.relation_enslavers.all()]))
				if len(enslaver_aliases_in_relation)>1:
					pass
# 					print("multi-relationship. skipping")
				else:
					enslaved_in_relation=[eir.enslaved.id for eir in relation.enslaved_in_relation.all()]
					enslaved_in_relation.sort()
					enslaver_roles=[role.name for role in relation.relation_enslavers.all().first().roles.all()]
					enslaver_roles.sort()
					voyage_id=relation.voyage_id
					enslaved_in_relation_dict[rel_id]={
						"enslaved_in_relation":enslaved_in_relation,
						"enslaver_roles":enslaver_roles,
						"voyage_id":voyage_id
					}
			
# 			if len(enslaved_in_relation_dict)>1:
# 				print(ea,json.dumps(enslaved_in_relation_dict,indent=2))
			
			cleaned=False
			while len(enslaved_in_relation_dict)>1:
# 				print('------')
# 				print(enslaved_in_relation_dict)
				rel_id=list(enslaved_in_relation_dict.keys())[0]
# 				print('REL ID-->',rel_id)
				reldict=enslaved_in_relation_dict.pop(rel_id)
				principal_rel=EnslavementRelation.objects.get(id=rel_id)
				delcompkeys=[]
				for rel_id_comp in enslaved_in_relation_dict:
					compdict=enslaved_in_relation_dict[rel_id_comp]
					if reldict['enslaver_roles']==compdict['enslaver_roles'] and reldict['voyage_id']==compdict['voyage_id']:
# 						print('DUPLICATES for:',ea.alias,ea.id)
# 						print('REL-->',rel_id,reldict)
# 						print('COMP-->',rel_id_comp,compdict)
						for enslaved_id in compdict['enslaved_in_relation']:
							ed=Enslaved.objects.get(id=enslaved_id)
							EnslavedInRelation.objects.create(
								relation=principal_rel,
								enslaved=ed
							)
						EnslavementRelation.objects.get(id=rel_id_comp).delete()
						delcompkeys.append(rel_id_comp)
						cleaned=True
				for delcompkey in delcompkeys:
					del(enslaved_in_relation_dict[delcompkey])
# 				print("after_dedupe--->",json.dumps(enslaved_in_relation_dict,indent=2))
			if cleaned:
				print(ea,ea.id)
						
					
		
		
#ALIAS WITH NEWLY-CONSOLIDATED RELATIONS, AS OF NOV 7
# EnslaverAlias: Talbot, William F. 56074
# EnslaverAlias: Gadn & Co?, James 59063
# EnslaverAlias: Farmer, John 1037774
# EnslaverAlias: Reed, James 1037775
# EnslaverAlias: Rollins, William 1037782
# EnslaverAlias: Wright, John T. 1037784
# EnslaverAlias: Barelli & Co. 1037788
# EnslaverAlias: Kelsey, D.S. 1037810
# EnslaverAlias: Blossman, R.D. 1037824
# EnslaverAlias: Windle, Henry 1037883
# EnslaverAlias: Tucker, J.B. 1037886
# EnslaverAlias: Wade, John 1037890
# EnslaverAlias: Crane, John R. 1037901
# EnslaverAlias: Dobbin, H.R. 1037904
# EnslaverAlias: Place, Henry 1037905
# EnslaverAlias: Lewis, S.B. 1037906
# EnslaverAlias: Phillips, John D. 1037913
# EnslaverAlias: Matson, J. 1037919
# EnslaverAlias: Smith, Jeremiah 1037937
# EnslaverAlias: Phillips, James D. 1037940
# EnslaverAlias: Boehner, H.E. 1037967
# EnslaverAlias: Robson, S.B. 1037992
# EnslaverAlias: Huard, H. 1038003
# EnslaverAlias: Jones, D.B. 1038057
# EnslaverAlias: Smith, J. 1038060
# EnslaverAlias: Blearson, Joseph 1038065
# EnslaverAlias: Peck, Thomas 1038075
# EnslaverAlias: Kelly, William 1038106
# EnslaverAlias: Guy, W.W. 1038112
# EnslaverAlias: Thompson, James A. 1038116
# EnslaverAlias: Felder, Samuel J. 1038118
# EnslaverAlias: Lincecun, L. 1038119
# EnslaverAlias: Glover, Edwin A. 1038120
# EnslaverAlias: Powell, S.G. 1038122
# EnslaverAlias: Peabody, D. 1038123
# EnslaverAlias: Toly, Simeon 1038125
# EnslaverAlias: Smyth, J.P. 1038126
# EnslaverAlias: Hawkins Jr., John D. 1038127
# EnslaverAlias: Sealey, J.B. 1038129
# EnslaverAlias: Sterns, W.H. 1038130
# EnslaverAlias: Hatch, George C. 1038131
# EnslaverAlias: Miller, Y.L. 1038132
# EnslaverAlias: Pippen, M.P. 1038134
# EnslaverAlias: Emerson, John 1038136
# EnslaverAlias: Watkins, S.C. 1038137
# EnslaverAlias: Dickson, Michael 1038138
# EnslaverAlias: Graves, L.C. 1038139
# EnslaverAlias: Tittle, J.L. 1038141
# EnslaverAlias: Turner, Jas. A. 1038143
# EnslaverAlias: Chandler, James 1038145
# EnslaverAlias: Buckley, C.A. 1038150
# EnslaverAlias: Beene, J. 1038151
# EnslaverAlias: Pinchback, John 1038152
# EnslaverAlias: Lewis, Mrs. 1038155
# EnslaverAlias: Stanley, L.C. 1038158
# EnslaverAlias: Nobels, W. 1038159
# EnslaverAlias: Britton, A 1038161
# EnslaverAlias: Holson, B.F. 1038163
# EnslaverAlias: Stoneum, George 1038165
# EnslaverAlias: Jones, Allen 1038166
# EnslaverAlias: Tryon, W.M. 1038167
# EnslaverAlias: Reed, Morgan James 1038169
# EnslaverAlias: Rutherford, C.M. 1038173
# EnslaverAlias: Wallis, Mrs. 1038177
# EnslaverAlias: Saunders, W.L. 1038179
# EnslaverAlias: Gibson, William 1038180
# EnslaverAlias: Jayns, J 1038183
# EnslaverAlias: Williams, John R. 1038184
# EnslaverAlias: Chadwick, J. N. 1038186
# EnslaverAlias: Jones, John 1038190
# EnslaverAlias: Baltte, Oliver L. 1038191
# EnslaverAlias: Flowers, J.E. 1038192
# EnslaverAlias: Hutchings, J. W. 1038193
# EnslaverAlias: Pollard, W.T. 1038196
# EnslaverAlias: Mayes, E.T. 1038197
# EnslaverAlias: Sharp, A.B. 1038201
# EnslaverAlias: Hickman, John 1038203
# EnslaverAlias: Douglass, H. 1038204
# EnslaverAlias: Thomas, M. 1038206
# EnslaverAlias: Metcalfe, John 1038207
# EnslaverAlias: Kendrick, J.A. 1038208
# EnslaverAlias: Smith, B. E. 1038210
# EnslaverAlias: Wooldridge, A.B. 1038212
# EnslaverAlias: Morse, John K. 1038213
EnslaverAlias: West, Hector R. 1038214
EnslaverAlias: Lenehan, M. 1038215
EnslaverAlias: Roberts, W. 1038217
EnslaverAlias: Walker, John B. 1038218
EnslaverAlias: Wood, A. H. 1038221
EnslaverAlias: Crisp, John H. 1038224
EnslaverAlias: Doak, J. 1038225
EnslaverAlias: George, W.L. 1038231
EnslaverAlias: Emerson, H. 1038233
EnslaverAlias: Reynaud, P. 1038234
EnslaverAlias: Sheppard, D.J. 1038235
EnslaverAlias: Robertson, C.T. 1038236
EnslaverAlias: Aldridge, L. 1038239
EnslaverAlias: Spurgin, John 1038240
EnslaverAlias: Kirkland, W.H. 1038241
EnslaverAlias: Donnellson, J. 1038242
EnslaverAlias: Jones, M 1038243
EnslaverAlias: Stoddard, J. W. 1038244
EnslaverAlias: Harris, E.A. 1038246
EnslaverAlias: Heath, J.G. 1038247
EnslaverAlias: Boaz, Josiah 1038248
EnslaverAlias: Edgar, James M. 1038249
EnslaverAlias: Morris. John A. 1038250
EnslaverAlias: McMillen, James 1038251
EnslaverAlias: Cunningham, A.J. 1038253
EnslaverAlias: Carter, Robert S. 1038254
EnslaverAlias: Walker, Daw. 1038255
EnslaverAlias: Davis, J.H. 1038256
EnslaverAlias: Hughes, John 1038257
EnslaverAlias: Ware, M. 1038259
EnslaverAlias: McGar, Talbot 1038260
EnslaverAlias: Payne, W.H. 1038262
EnslaverAlias: Hall, T.D. 1038263
EnslaverAlias: Wilcox, George 1038264
EnslaverAlias: Halphen, Jacob 1038265
EnslaverAlias: Baylor, G.H. 1038266
EnslaverAlias: Davis, W.A. 1038268
EnslaverAlias: Hayward, G.A. 1038270
EnslaverAlias: McGar, John 1038272
EnslaverAlias: Wallace, J.L. 1038273
EnslaverAlias: Herring, Samuel 1038275
EnslaverAlias: Burt, J.J. 1038276
EnslaverAlias: Farmer, William D. 1038278
EnslaverAlias: Rocca, L 1038279
EnslaverAlias: Lee, John 1038281
EnslaverAlias: Hinton, Samuel 1038284
EnslaverAlias: Connerly, H. 1038285
EnslaverAlias: Snell, A 1038287
EnslaverAlias: Parrott, Thomas Y. 1038290
EnslaverAlias: Clayton, John M. 1038292
EnslaverAlias: Porter, D.M. 1038293
EnslaverAlias: Bonner, John 1038294
EnslaverAlias: Mayes, R. L. 1038295
EnslaverAlias: Harvey, James A. 1038296
EnslaverAlias: Foster, W.J. 1038298
EnslaverAlias: Darrington, J. 1038300
EnslaverAlias: Dudley, F.W. 1038301
EnslaverAlias: Aycock, Mrs. 1038303
EnslaverAlias: Krepff, John 1038304
EnslaverAlias: Jarvis, N. S. 1038307
EnslaverAlias: Dickson, Thomas 1038308
EnslaverAlias: Sampson, S. 1038309
EnslaverAlias: Noble, F. 1038311
EnslaverAlias: Penn, R.A. 1038312
EnslaverAlias: Johnson, William 1038313
EnslaverAlias: Persons, L.S. 1038314
EnslaverAlias: Dryer, Achilles H. 1038315
EnslaverAlias: Wilson, H.R. 1038316
EnslaverAlias: Gautier, Dr. W.J. 1038318
EnslaverAlias: Goodrich, P.M. 1038319
EnslaverAlias: Nelson & Co. 1038320
EnslaverAlias: Kinney, P.M. 1038321
EnslaverAlias: Biscoe, A.H. 1038323
EnslaverAlias: McDuffie, N.K. 1038324
EnslaverAlias: Mayers, A.G. 1038326
EnslaverAlias: Mizell, A. 1038334
EnslaverAlias: Hatch, S. 1038335
EnslaverAlias: Risher, B.A. 1038336
EnslaverAlias: Sample, Joseph 1038337
EnslaverAlias: Gray, Allen 1038338
EnslaverAlias: Manderill, Charles G. 1038341
EnslaverAlias: Lynch, F.J. 1038342
EnslaverAlias: Moore, Robert D. 1038345
EnslaverAlias: Williams, Dr. A. 1038346
EnslaverAlias: Harral, W. 1038347
EnslaverAlias: Buntin, William F. 1038348
EnslaverAlias: Thornhill, S.F. 1038350
EnslaverAlias: Bryant, J.A. 1038353
EnslaverAlias: White, David 1038355
EnslaverAlias: Oats, Caraway 1038357
EnslaverAlias: Barelli, J.S. 1038358
EnslaverAlias: Sullivan, R.H. 1038360
EnslaverAlias: Bateman, James W. 1038361
EnslaverAlias: Ganabi, Charles 1038363
EnslaverAlias: Lorrel, R. H. D 1038366
EnslaverAlias: Brissmann, S.H. 1038367
EnslaverAlias: Robinson, Levi 1038368
EnslaverAlias: Buckner, B.P. 1038374
EnslaverAlias: Brown, William 1038375
EnslaverAlias: Kay, William 1038376
EnslaverAlias: Alma, Leon R. 1038380
EnslaverAlias: Haviland, J. E. 1038381
EnslaverAlias: Dunlap, J.G. 1038382
EnslaverAlias: Benter, John 1038385
EnslaverAlias: Pringle, William L. 1038386
EnslaverAlias: Sherman, S. 1038387
EnslaverAlias: Baker, A. C. 1038389
EnslaverAlias: McNeil, James A. 1038392
EnslaverAlias: Decrow, Thomas 1038393
EnslaverAlias: Gilmore, William M. 1038395
EnslaverAlias: Elliott, E P. 1038397
EnslaverAlias: Bookman, Jesse 1038398
EnslaverAlias: Mitchell, S.D. 1038399
EnslaverAlias: Feagin, Aaron 1038400
EnslaverAlias: Smith, William R. 1038401
EnslaverAlias: Isaac Parks 1038402
EnslaverAlias: Phaill, W.W.M. 1038403
EnslaverAlias: Thomas, John C. 1038404
EnslaverAlias: Lindsay, L. 1038410
EnslaverAlias: Shelby, John O. 1038411
EnslaverAlias: Owen, Clark S. 1038413
EnslaverAlias: Edwards, H.W. 1038416
EnslaverAlias: Grayson, W. P. 1038417
EnslaverAlias: Wheeler, J. A. 1038418
EnslaverAlias: Hyan, W.C. 1038419
EnslaverAlias: Hanna, Archibald 1038420
EnslaverAlias: Patterson, T. 1038422
EnslaverAlias: Check, N. 1038424
EnslaverAlias: Campbell, James 1038425
EnslaverAlias: McLemon, D.J. 1038426
EnslaverAlias: Graves, John L. 1038427
EnslaverAlias: Carmichael, H.M. 1038431
EnslaverAlias: Tate, Fred 1038439
EnslaverAlias: Sampson, Samuel 1038440
EnslaverAlias: McClosky, William 1038444
EnslaverAlias: Adams, Ballad 1038445
EnslaverAlias: Colles, J. H. 1038446
EnslaverAlias: Edwards, P.R. 1038448
EnslaverAlias: Layton, Robert A. 1038450
EnslaverAlias: Scoofy, Jane 1038453
EnslaverAlias: White, John P. 1038454
EnslaverAlias: Criswell, Thomas 1038455
EnslaverAlias: Mattison, G.P. 1038456
EnslaverAlias: Horton, Albert C. 1038457
EnslaverAlias: Allen, Thompson 1038459
EnslaverAlias: Reid, J.M. 1038460
EnslaverAlias: Cocker, William 1038462
EnslaverAlias: Martin, H.B. 1038463
EnslaverAlias: Mason, Samuel 1038465
EnslaverAlias: Powell, James G. 1038468
EnslaverAlias: DePoorter, L. 1038469
EnslaverAlias: Kindred, J.P. 1038472
EnslaverAlias: Tichenor, S.H. 1038477
EnslaverAlias: Fulton, Z.K. 1038479
EnslaverAlias: Pruitt, James L. 1038480
EnslaverAlias: Baldridge, J.W. 1038481
EnslaverAlias: Trunstall, J. J. 1038482
EnslaverAlias: Vauzile, John 1038483
EnslaverAlias: Browning, A.M. 1038487
EnslaverAlias: Williams, A.J. 1038492
EnslaverAlias: Green, Wilson 1038497
EnslaverAlias: McNair, R.H. 1038498
EnslaverAlias: Easley, Samuel A. 1038501
EnslaverAlias: Harris, Lewis 1038502
EnslaverAlias: Swan, James L. 1038504
EnslaverAlias: Stringfellow, H. 1038505
EnslaverAlias: Crowell, E. 1038506
EnslaverAlias: Menard, M.B. 1038508
EnslaverAlias: Hardy, Robert L. 1038509
EnslaverAlias: Byrons, J.S.C. 1038510
EnslaverAlias: Warren, George 1038512
EnslaverAlias: Morris, A.T. 1038514
EnslaverAlias: Ulrich, J. 1038515
EnslaverAlias: Turner, James A. 1038517
EnslaverAlias: Arnold, William 1038518
EnslaverAlias: Bringham 1038519
EnslaverAlias: Battle, N.W. 1038520
EnslaverAlias: Counsel, Renford 1038521
EnslaverAlias: Wells, Henry C. 1038522
EnslaverAlias: Wilson, W. 1038523
EnslaverAlias: Wade, Joseph D. 1038524
EnslaverAlias: Dudley, A. E. 1038525
EnslaverAlias: Sumner, Sam 1038527
EnslaverAlias: Sims, F. 1038528
EnslaverAlias: Stidham, Lewis 1038530
EnslaverAlias: Makley, M. 1038532
EnslaverAlias: Penland, N.A. 1038533
EnslaverAlias: Read, W.S. 1038536
EnslaverAlias: Dowell, Dr. G. 1038537
EnslaverAlias: Hare, Thomas J. 1038541
EnslaverAlias: Freeman, N. 1038542
EnslaverAlias: Hanna, Josiah 1038543
EnslaverAlias: Liles, J. T. 1038546
EnslaverAlias: Winston, John L. 1038548
EnslaverAlias: Bell, Bennett 1038550
EnslaverAlias: Anderson, J.M. 1038551
EnslaverAlias: Silversides, Robert 1038556
EnslaverAlias: Robson, J.R. 1038557
EnslaverAlias: Hampton, D.W. 1038559
EnslaverAlias: Pope, W.S. 1038560
EnslaverAlias: Moore, Thomas C. 1038561
EnslaverAlias: Bray, John 1038563
EnslaverAlias: Messina, Am 1038564
EnslaverAlias: Hicklin, Thomas.J. 1038565
EnslaverAlias: Elder, Thomas G. 1038566
EnslaverAlias: Scranton 1038568
EnslaverAlias: McElroy, John 1038569
EnslaverAlias: Elder, J.W. 1038570
EnslaverAlias: McDowell, G.A. 1038572
EnslaverAlias: George, J.W. 1038573
EnslaverAlias: Wilson, H. 1038574
EnslaverAlias: Autry, A.B. 1038575
EnslaverAlias: Shaver, Henry P. 1038576
EnslaverAlias: Cuvellier, Charles 1038577
EnslaverAlias: Skinner, W. H. 1038578
EnslaverAlias: Banton, William 1038580
EnslaverAlias: Venable, W.G. 1038581
EnslaverAlias: McDonald, John W. 1038584
EnslaverAlias: Hill, John C. 1038587
EnslaverAlias: Young, Robert 1038588
EnslaverAlias: Parker, W. 1038590
EnslaverAlias: Sanders, R.M. 1038593
EnslaverAlias: Gresham, Joseph 1038594
EnslaverAlias: Groesbeck, A. 1038595
EnslaverAlias: Anderson, M.D. 1038596
EnslaverAlias: Hoxey, John J.B. 1038597
EnslaverAlias: Angell, James 1038598
EnslaverAlias: Burkly, N.W. 1038601
EnslaverAlias: Bryan, John 1038606
EnslaverAlias: Sorenton, F. 1038607
EnslaverAlias: Little, Robert 1038608
EnslaverAlias: Jamry, P.P.G 1038609
EnslaverAlias: Cottrell, J.L. 1038610
EnslaverAlias: Stokes, Thomas 1038611
EnslaverAlias: Tinsley, J.C. 1038613
EnslaverAlias: Stewart, William H. 1038614
EnslaverAlias: French, Marcellus 1038615
EnslaverAlias: Jones, William H. 1038616
EnslaverAlias: Warren, S.H.D. 1038617
EnslaverAlias: Bailey, John H. 1038618
EnslaverAlias: Chambers, George C. 1038619
EnslaverAlias: Robinson, J.H. 1038620
EnslaverAlias: Westmoreland, T.J. 1038621
EnslaverAlias: Irwin, William 1038622
EnslaverAlias: Wesley, C. C. 1038624
EnslaverAlias: Allen, NB 1038625
EnslaverAlias: Hillard, J.E. 1038627
EnslaverAlias: Price, John F. 1038628
EnslaverAlias: Weston, A.G. 1038629
EnslaverAlias: Baudue, F. J. 1038631
EnslaverAlias: Hall, Thomas 1038634
EnslaverAlias: Martin, A.G. 1038635
EnslaverAlias: Underwood, Anderson 1038637
EnslaverAlias: Douglass, H.W. 1038638
EnslaverAlias: Foster, James M. 1038639
EnslaverAlias: Stevens, W.H. 1038640
EnslaverAlias: Tate, J.T. 1038643
EnslaverAlias: Smith, Samuel W. 1038644
EnslaverAlias: Fulton, Francis P. 1038647
EnslaverAlias: Terver, Thomas 1038648
EnslaverAlias: Waul, T.N. 1038650
EnslaverAlias: West, S.S. 1038653
EnslaverAlias: Windle, H. 1038657
EnslaverAlias: Williams, R.H. 1038658
EnslaverAlias: Flournay, John 1038662
EnslaverAlias: Ewing, John 1038664
EnslaverAlias: Moody, D.J. 1038665
EnslaverAlias: Hartridge, H.E. 1038666
EnslaverAlias: Hamilton, John A. 1038668
EnslaverAlias: Logan, J.L.N. 1038670
EnslaverAlias: Hansbrough, W.S. 1038672
EnslaverAlias: Puddy, Mrs Mary Arriman 1038673
EnslaverAlias: Bradley and Wilson 1038675
EnslaverAlias: Tais, James 1038677
EnslaverAlias: Hite, S.N. 1038678
EnslaverAlias: Plummer, J.R. 1038679
EnslaverAlias: Word, C.G. 1038680
EnslaverAlias: Snodgrass, Sam 1038683
EnslaverAlias: Runnels, H.G. 1038684
EnslaverAlias: Almy, Leon A. 1038686
EnslaverAlias: Shann, C.C. 1038687
EnslaverAlias: Spurlin, J.J. 1038690
EnslaverAlias: Jones, V.R. 1038694
EnslaverAlias: Shaw, E.P. 1038698
EnslaverAlias: Wagner, F. H. 1038702
EnslaverAlias: Bradley, R. 1038704
EnslaverAlias: Tate, J. McD 1038705
EnslaverAlias: Brothers, R.J. 1038706
EnslaverAlias: Nance, T.H. 1038707
EnslaverAlias: Moon Tites & Co. 1038712
EnslaverAlias: Newman, Warren 1038714
EnslaverAlias: Pinkston, James B. 1038716
EnslaverAlias: Swiler, J. 1038717
EnslaverAlias: Anthony, H.S. 1038718
EnslaverAlias: Nelson and Co 1038720
EnslaverAlias: Athin, Nathaniel 1038721
EnslaverAlias: Alexander, E.B. 1038727
EnslaverAlias: Hunter, J.L. 1038728
EnslaverAlias: Lobdell, J.V. 1038729
EnslaverAlias: Knighton, Moses G. 1038730
EnslaverAlias: Augusto, Francois 1038731
EnslaverAlias: Wagnon, J.H. 1038734
EnslaverAlias: Barnett, Charles J. 1038737
EnslaverAlias: Staunchfield, Bartley 1038739
EnslaverAlias: McLeary, Samuel D. 1038740
EnslaverAlias: Parsons, Silas 1038741
EnslaverAlias: Chappell, R.M. 1038744
EnslaverAlias: Lacy, Thomas H. 1038745
EnslaverAlias: Burnwall, Henry 1038746
EnslaverAlias: Smith, H.J. 1038747
EnslaverAlias: Foster, A.H. 1038749
EnslaverAlias: Terry, B. 1038750
EnslaverAlias: Miller, Henry V. 1038751
EnslaverAlias: Harmon, William B.N. 1038754
EnslaverAlias: Calhoun, P.B. 1038756
EnslaverAlias: Cecil, B. 1038758
EnslaverAlias: Winston, Isaac W. 1038761
EnslaverAlias: Scott, Joseph 1038762
EnslaverAlias: Seawell, S.T. 1038763
EnslaverAlias: Smith, M. L. 1038764
EnslaverAlias: Fields, William 1038769
EnslaverAlias: Singeltary, John W. 1038771
EnslaverAlias: McKenny, E 1038772
EnslaverAlias: Massongale, A.M. 1038773
EnslaverAlias: McDaniel, Adam 1038774
EnslaverAlias: Christian, William M. 1038777
EnslaverAlias: Bryce, Wm 1038784
EnslaverAlias: Foote, Richard H. 1038790
EnslaverAlias: Davidson, William 1038793
EnslaverAlias: Payne, J.F. 1038794
EnslaverAlias: Pitts, Jesse 1038795
EnslaverAlias: Brazil, W.S. 1038796
EnslaverAlias: Broaddus, M. 1038799
EnslaverAlias: Cottingham, F.M. 1038801
EnslaverAlias: McMahon, J.J. 1038802
EnslaverAlias: Stevens, John 1038804
EnslaverAlias: Nelson, R. C. 1038806
EnslaverAlias: Bell, P.H. 1038807
EnslaverAlias: Platt, R.B. 1038808
EnslaverAlias: Hatcher, J. 1038809
EnslaverAlias: Bennett, A.T. 1038810
EnslaverAlias: Bell, James H. 1038811
EnslaverAlias: Warfield, Jr., E. 1038812
EnslaverAlias: Brown, L.F. 1038815
EnslaverAlias: McColloch, John S. 1038818
EnslaverAlias: Hawkins, Jas. B. 1038821
EnslaverAlias: Terry, Benjamin 1038824
EnslaverAlias: Goodrich, B.G. 1038825
EnslaverAlias: Turner, A. 1038826
EnslaverAlias: Stafford, Bud 1038827
EnslaverAlias: McDowell, William 1038829
EnslaverAlias: Wright, J.T. 1038835
EnslaverAlias: Jammon, R.B. 1038838
EnslaverAlias: Hamilton, T. Lynell 1038840
EnslaverAlias: Moseley, T.R. 1038842
EnslaverAlias: Elmore, H.M. 1038843
EnslaverAlias: Wise, Charles S. 1038844
EnslaverAlias: Jones, William J. 1038846
EnslaverAlias: Windsor, James 1038847
EnslaverAlias: Riddle, H. 1038848
EnslaverAlias: Sharp, M.L.F. 1038849
EnslaverAlias: Hobdy, William 1038850
EnslaverAlias: Dunlavy, Henry 1038851
EnslaverAlias: Stewart, D.D. 1038853
EnslaverAlias: Caplan, Rebecca 1038855
EnslaverAlias: Williams, L.E.S. 1038857
EnslaverAlias: Lee, George S. 1038858
EnslaverAlias: English, R. B. 1038859
EnslaverAlias: Ramsey, Martin D. 1038860
EnslaverAlias: Keyser, George 1038863
EnslaverAlias: Hubbard, B.M. 1038865
EnslaverAlias: Randle, J.R. 1038866
EnslaverAlias: Grayson, S.G. 1038867
EnslaverAlias: Delano, William 1038868
EnslaverAlias: Lamarque, Charles 1038871
EnslaverAlias: Hogg, W.G. 1038872
EnslaverAlias: Harris, J.B. 1038873
EnslaverAlias: Thornhill, H. 1038874
EnslaverAlias: Morrison, J.W. 1038876
EnslaverAlias: Morris, John D. 1038877
EnslaverAlias: McGahey, A. 1038881
EnslaverAlias: Hamilton, S.F. 1038882
EnslaverAlias: McGovern, E. 1038883
EnslaverAlias: Rhiney, Wm. C. 1038884
EnslaverAlias: Clark, D.C. 1038885
EnslaverAlias: Elliot, William 1038886
EnslaverAlias: Brown, John B. 1038888
EnslaverAlias: Moore, James 1038891
EnslaverAlias: Graybill, J. 1038893
EnslaverAlias: Harper, Richard 1038894
EnslaverAlias: Goodlette, W.C. 1038895
EnslaverAlias: Sexton, William 1038896
EnslaverAlias: Morris, J.D. 1038898
EnslaverAlias: Love, R.O. 1038899
EnslaverAlias: McDow, John R. 1038904
EnslaverAlias: Lockett, Thomas J. 1038906
EnslaverAlias: Pool, J.L. 1038908
EnslaverAlias: Yager, W. O. 1038909
EnslaverAlias: Stewart, James W. 1038910
EnslaverAlias: Tarver, B.J. 1038911
EnslaverAlias: Ingram, W.P. 1038913
EnslaverAlias: Moore, A.L.D. 1038914
EnslaverAlias: Show, Col. Tomas H. 1038916
EnslaverAlias: Smith Harris and Co 1038917
EnslaverAlias: Randolph, J. 1038918
EnslaverAlias: Grace, T.J. 1038920
EnslaverAlias: Perry, A.J. 1038921
EnslaverAlias: Crane, John R. 1038923
EnslaverAlias: McCarty, A.T.M. 1038924
EnslaverAlias: Solomon, L.J. 1038925
EnslaverAlias: Keene, E.Y. 1038927
EnslaverAlias: Roberts, J.F. 1038928
EnslaverAlias: Barnett, William 1038929
EnslaverAlias: Hanchfield, Bartley 1038930
EnslaverAlias: Smith, A. 1038931
EnslaverAlias: Hoffman, Solomon 1038932
EnslaverAlias: Obermar, Thomas 1038933
EnslaverAlias: Atchison, D.D. 1038934
EnslaverAlias: Allen, Jas. 1038938
EnslaverAlias: Hebert, Mrs. 1038940
EnslaverAlias: Sellers, John N. 1038941
EnslaverAlias: Lockett, Stephen C. 1038945
EnslaverAlias: Behn, G.W. 1038948
EnslaverAlias: Wadde, J.P. 1038950
EnslaverAlias: Crawley, James 1038951
EnslaverAlias: Sawyer, Sarah 1038952
EnslaverAlias: Morton, Thomas 1038953
EnslaverAlias: Greer, W.C. 1038954
EnslaverAlias: Hanks, A. 1038956
EnslaverAlias: Pyers, J.B. 1038957
EnslaverAlias: Harper, R.A. 1038958
EnslaverAlias: Gillespie, J.B. 1038959
EnslaverAlias: Sayers, David 1038960
EnslaverAlias: Gay, Thomas A. 1038961
EnslaverAlias: Ivey, Tilitha 1038962
EnslaverAlias: Powell, H.J. 1038963
EnslaverAlias: Sawyer, W. E. 1038965
EnslaverAlias: Spence, John 1038969
EnslaverAlias: Chapman, P.H.H. 1038971
EnslaverAlias: Mitchel, D.L. 1038972
EnslaverAlias: Turner, S. 1038973
EnslaverAlias: Snell, Amos 1038976
EnslaverAlias: Washington, G. 1038977
EnslaverAlias: Forshey, C.G. 1038978
EnslaverAlias: Kerchuel, J.J. 1038980
EnslaverAlias: Pritchard, Carroll 1038981
EnslaverAlias: Blair, Thomas M. 1038983
EnslaverAlias: Foster, J.D. 1038985
EnslaverAlias: Heard, Joel 1038986
EnslaverAlias: Simpson, J.P. 1038987
EnslaverAlias: Talbot, J.V. 1038990
EnslaverAlias: Smith, J. 1038994
EnslaverAlias: Claiborne, T. 1038995
EnslaverAlias: Kinaer, A. 1038996
EnslaverAlias: Allen, W.F. 1038999
EnslaverAlias: Lanham, M. 1039000
EnslaverAlias: Warfield, E 1039002
EnslaverAlias: Reed, J.W. 1039005
EnslaverAlias: Baldwin, D.J. 1039006
EnslaverAlias: Strange, C.D. 1039008
EnslaverAlias: Walters, G.T. 1039009
EnslaverAlias: Pilsbury, E. 1039010
EnslaverAlias: Benorst, Mrs. 1039011
EnslaverAlias: Thomas, J.H. 1039012
EnslaverAlias: Ewing, Alex 1039014
EnslaverAlias: Speir, Willis 1039015
EnslaverAlias: Dromgoole, P.G. 1039016
EnslaverAlias: McGee, J.G.L. 1039018
EnslaverAlias: Wingfield, J.W. 1039020
EnslaverAlias: Jump, F.E. 1039021
EnslaverAlias: Cardwell, John 1039026
EnslaverAlias: Weyman, J.B. 1039028
EnslaverAlias: Ransom, J.P. 1039029
EnslaverAlias: Daniel, Jasper N. 1039030
EnslaverAlias: Manly, L.C. 1039031
EnslaverAlias: Dowell, G. 1039032
EnslaverAlias: Stewart, W.B. 1039033
EnslaverAlias: Moore, W.B. 1039038
EnslaverAlias: Hawes, H.W. 1039039
EnslaverAlias: Brown, John Wilson 1039040
EnslaverAlias: Tucker, H. 1039042
EnslaverAlias: Hayes, P.H. 1039043
EnslaverAlias: Winston, Fountain 1039045
EnslaverAlias: French, James 1039047
EnslaverAlias: Arrington, J. 1039048
EnslaverAlias: Scott, James N. 1039050
EnslaverAlias: Smith, F.E. 1039051
EnslaverAlias: Hines, B.J. 1039052
EnslaverAlias: Chambliss, N. 1039054
EnslaverAlias: Presler, James M. 1039055
EnslaverAlias: McGrew, W.P. 1039057
EnslaverAlias: Wilson, J.L. 1039059
EnslaverAlias: Tyson, John E. 1039060
EnslaverAlias: Gerald, G.S. 1039061
EnslaverAlias: Sample, Robert 1039062
EnslaverAlias: Jackson, W.H. 1039063
EnslaverAlias: Hays, John 1039064
EnslaverAlias: Meriwether, W.H. 1039066
EnslaverAlias: Fanton, A.B. 1039067
EnslaverAlias: Schiener, T. 1039070
EnslaverAlias: Greenlaw, A. 1039072
EnslaverAlias: Bishop, William N. 1039075
EnslaverAlias: Whitfield, H.H. 1039076
EnslaverAlias: McNeel, L.H. 1039077
EnslaverAlias: Connolly, Thomas 1039078
EnslaverAlias: Eborn, T. 1039079
EnslaverAlias: Phillips, Z. 1039080
EnslaverAlias: Campbell, F. 1039082
EnslaverAlias: Lowe, James C. 1039086
EnslaverAlias: Miller, B.R. 1039087
EnslaverAlias: Lewis, T.H. 1039088
EnslaverAlias: Denman, S.J. 1039091
EnslaverAlias: Steen, Enoch 1039092
EnslaverAlias: Newcomb, P. 1039094
EnslaverAlias: McDuffy, H. 1039095
EnslaverAlias: Carr, Allen 1039097
EnslaverAlias: Greylier, William 1039099
EnslaverAlias: Hill, Henry 1039100
EnslaverAlias: Chochran, James 1039106
EnslaverAlias: Spinlock, James 1039107
EnslaverAlias: Butcher, Dr. J.C. 1039109
EnslaverAlias: Bostick, Richard James 1039110
EnslaverAlias: Brown, Charles P. 1039111
EnslaverAlias: Isaacs, A.C. 1039114
EnslaverAlias: Matchet, J.F. 1039119
EnslaverAlias: Lackey, Sam C. 1039120
EnslaverAlias: Railey, Lewis C. 1039123
EnslaverAlias: Gillespie, J.H. 1039124
EnslaverAlias: Parnall, James C. 1039127
EnslaverAlias: Rains, G. C. 1039129
EnslaverAlias: Parke, Hezekiah 1039133
EnslaverAlias: Whilden, J.T. 1039134
EnslaverAlias: Louis, Jean 1039136
EnslaverAlias: Skaggs, A.M. 1039139
EnslaverAlias: Gass, Ben 1039143
EnslaverAlias: Cockrum, W.W. 1039144
EnslaverAlias: Mills, Samuel 1039146
EnslaverAlias: Glatigny, E. 1039148
EnslaverAlias: Rivers, Robert J. 1039150
EnslaverAlias: Davis, J.R. 1039152
EnslaverAlias: Crawley, James D. 1039154
EnslaverAlias: Cornell, S. 1039156
EnslaverAlias: Lawson, John A. 1039157
EnslaverAlias: McNair, Daniel 1039159
EnslaverAlias: Smith, St. M. 1039160
EnslaverAlias: Harvey, Colle M 1039162
EnslaverAlias: Lane, S.N. 1039164
EnslaverAlias: Barnes, J. H. 1039168
EnslaverAlias: Jones, A.W. 1039170
EnslaverAlias: Greenwood, Charles and Caldwell 1039171
EnslaverAlias: Cirode, Mrs. Mary Ann 1039173
EnslaverAlias: Ballard, C. 1039175
EnslaverAlias: Murray, R.C. 1039176
EnslaverAlias: Sample, Alexander 1039177
EnslaverAlias: Winn, Thomas 1039179
EnslaverAlias: Connor, J.T. 1039184
EnslaverAlias: Blackson, J.D. 1039186
EnslaverAlias: Wilson, Thomas D. 1039188
EnslaverAlias: Ewing, A.G. 1039189
EnslaverAlias: Gordon, Jesse S. 1039190
EnslaverAlias: Ward, S. 1039192
EnslaverAlias: Wade, Wm. F. 1039193
EnslaverAlias: Holstead, J. 1039195
EnslaverAlias: VanBolokilen, Capt. M. 1039197
EnslaverAlias: Bassett, Ben H. 1039198
EnslaverAlias: Heaney, P. 1039201
EnslaverAlias: Forest, M.B. 1039204
EnslaverAlias: Denny, R.J. 1039208
EnslaverAlias: Schler, George H. 1039213
EnslaverAlias: Smith, J. P. 1039215
EnslaverAlias: Sorley, James 1039217
EnslaverAlias: Groce, James 1039219
EnslaverAlias: Vivian, T. 1039222
EnslaverAlias: Bond, J.C.P. 1039223
EnslaverAlias: Darden, W.J. 1039224
EnslaverAlias: Wilcox, J.A. 1039226
EnslaverAlias: Scranton, H. 1039228
EnslaverAlias: Simmons, J.M. 1039230
EnslaverAlias: Trigg, A.S. 1039232
EnslaverAlias: Wheeler, O.M. 1039233
EnslaverAlias: Humphreys, B.W. 1039237
EnslaverAlias: Dromgoole, P. H. 1039242
EnslaverAlias: Tarbox, S. 1039243
EnslaverAlias: Chambers, John H. 1039244
EnslaverAlias: Vickers, H.J. 1039245
EnslaverAlias: Holiday, S. 1039246
EnslaverAlias: Calloway, A.C. 1039247
EnslaverAlias: Wilkinson, James 1039249
EnslaverAlias: Dunlap, S.C. 1039252
EnslaverAlias: Dane, J.H. 1039255
EnslaverAlias: Reed, Henry 1039256
EnslaverAlias: Rives, N.E. 1039257
EnslaverAlias: Johnston, A.A. 1039259
EnslaverAlias: Gardner, J.P. 1039260
EnslaverAlias: McClintock, J.R. 1039261
EnslaverAlias: Ross, G.A. 1039262
EnslaverAlias: Locklin, Wm. L. 1039268
EnslaverAlias: Hamilton, G. 1039270
EnslaverAlias: De Castro, Gregory 1039272
EnslaverAlias: Prince, Kimball 1039274
EnslaverAlias: Broadnax, R. 1039276
EnslaverAlias: Fisher, L.D. 1039277
EnslaverAlias: Arnold, William J. 1039278
EnslaverAlias: Torrance, R.A. 1039279
EnslaverAlias: White, John R. 1039280
EnslaverAlias: Faglie, Richard 1039282
EnslaverAlias: Agnes, David 1039283
EnslaverAlias: Paul, G.R. 1039284
EnslaverAlias: Wood, William R. 1039287
EnslaverAlias: Bolton, Charles L. 1039292
EnslaverAlias: Barton, C. 1039293
EnslaverAlias: Binns, John 1039295
EnslaverAlias: Effinger, Ta. 1039299
EnslaverAlias: Davis, John W. 1039300
EnslaverAlias: Bedwell, J.M. 1039302
EnslaverAlias: Miller W.B. 1039307
EnslaverAlias: O'Hara John 1039310
EnslaverAlias: Doran, John 1039311
EnslaverAlias: McFee, James 1039314
EnslaverAlias: Thurmond, P.H. 1039315
EnslaverAlias: Randle, L. C. 1039316
EnslaverAlias: Logan, J. L. N. 1039318
EnslaverAlias: Clark, George 1039319
EnslaverAlias: Nusom, T.A. 1039320
EnslaverAlias: Beal, J. William M. 1039321
EnslaverAlias: Bank, John B 1039324
EnslaverAlias: Price, W.B. 1039325
EnslaverAlias: Bennett, Walter 1039327
EnslaverAlias: Cain, John H. 1039328
EnslaverAlias: Hewson, Alfred 1039331
EnslaverAlias: Martin, John 1039332
EnslaverAlias: Moore, L.L. 1039333
EnslaverAlias: Talbot, William 1039334
EnslaverAlias: Magruder, N.B. 1039338
EnslaverAlias: Lowe, B.M. 1039340
EnslaverAlias: Augustin Toutant 1039341
EnslaverAlias: Maury, D.H. 1039343
EnslaverAlias: Atkinson, Isaac H. 1039345
EnslaverAlias: Bryan, Nathan 1039347
EnslaverAlias: Scott, James W. 1039348
EnslaverAlias: King, Nathan 1039349
EnslaverAlias: Cabell, A.S. 1039350
EnslaverAlias: Smith, Mrs. 1039354
EnslaverAlias: Baxter, B.B. 1039361
EnslaverAlias: Baker, J.W. 1039362
EnslaverAlias: Fulford, W.T. 1039363
EnslaverAlias: Lex, John P. 1039364
EnslaverAlias: Burbank, James 1039366
EnslaverAlias: Rogers, E.W. 1039367
EnslaverAlias: Boshua, William 1039368
EnslaverAlias: Kelley, William 1039369
EnslaverAlias: Henderson, E. 1039370
EnslaverAlias: Hughes, J.H. 1039372
EnslaverAlias: Fretwell, John K. 1039376
EnslaverAlias: Hill, W.J. 1039379
EnslaverAlias: Nicholson, M.H. 1039381
EnslaverAlias: Sydnor, John S. 1039384
EnslaverAlias: Adams, John 1039386
EnslaverAlias: Kearney, Alfred 1039387
EnslaverAlias: Hale, Elizabeth 1039388
EnslaverAlias: Moore, W.F. 1039390
EnslaverAlias: Blair, James D. 1039391
EnslaverAlias: Effinger, Frances 1039392
EnslaverAlias: Franklin, B.J. 1039394
EnslaverAlias: Peck, McDowell 1039395
EnslaverAlias: Flewellen, R.J. 1039396
EnslaverAlias: McLeran, John 1039397
EnslaverAlias: Swalle, A. 1039399
EnslaverAlias: Berryhill, Isaac 1039402
EnslaverAlias: Holliday, Thomas 1039405
EnslaverAlias: Stoner, M. L. 1039406
EnslaverAlias: Elliott Jr. T.A. 1039407
EnslaverAlias: Villenueve, C. 1039408
EnslaverAlias: Stith, M.S. 1039409
EnslaverAlias: Dunovant, A. Q. 1039410
EnslaverAlias: Callahan, Michael 1039411
EnslaverAlias: Hill, J. 1039418
EnslaverAlias: Bell, Christopher C. 1039420
EnslaverAlias: Keene, B.C. 1039422
EnslaverAlias: Baylor, W.G. 1039423
EnslaverAlias: Jones, Levi 1039424
EnslaverAlias: McDougal, John 1039428
EnslaverAlias: McKnight, Thomas 1039430
EnslaverAlias: Fish, W.J. 1039432
EnslaverAlias: Matthews, H.F. 1039433
EnslaverAlias: Wilson, R.B. 1039435
EnslaverAlias: Boulware, William H. 1039436
EnslaverAlias: Hardee, Captain William 1039437
EnslaverAlias: Watson, R.H. 1039438
EnslaverAlias: Rice, Thomas J. 1039439
EnslaverAlias: Barnes, C. 1039442
EnslaverAlias: Canfield, W.E. 1039443
EnslaverAlias: Scranton, F. 1039445
EnslaverAlias: Bonner, J. 1039446
EnslaverAlias: Shearer, Henry 1039447
EnslaverAlias: Killough, J. 1039448
EnslaverAlias: Perry, P. 1039452
EnslaverAlias: Beale, Lloyd 1039453
EnslaverAlias: Hudgins, H. 1039454
EnslaverAlias: Brown, Bartlbe 1039455
EnslaverAlias: Gandy, Daniel 1039457
EnslaverAlias: White, William H. 1039460
EnslaverAlias: LeGrand, W.T. 1039461
EnslaverAlias: Cleveland, T.J. 1039468
EnslaverAlias: Neill, Andrew 1039469
EnslaverAlias: Brodmax, Dr. Robert 1039470
EnslaverAlias: McCulloch, M.J. 1039473
EnslaverAlias: Crabb, H.A. 1039475
EnslaverAlias: Hanell, W.H. 1039476
EnslaverAlias: Thompson, O.L.P. 1039480
EnslaverAlias: Foote, Stephen D. 1039482
EnslaverAlias: Jones, R.P. 1039485
EnslaverAlias: Bryan, C.C. 1039486
EnslaverAlias: Marshall, John 1039492
EnslaverAlias: Eustace, Joseph N. 1039494
EnslaverAlias: Radford, John P. 1039497
EnslaverAlias: Gass, Benjamin 1039498
EnslaverAlias: Gooch, J.G. 1039499
EnslaverAlias: Coffey, A. 1039501
EnslaverAlias: Grace, B.M. 1039502
EnslaverAlias: Midlock, Alfred 1039503
EnslaverAlias: McNeal, John G. 1039504
EnslaverAlias: Moore, Samuel A. 1039507
EnslaverAlias: Hill, A.W. 1039508
EnslaverAlias: Ryan, J.W. 1039510
EnslaverAlias: Stafford, A. 1039512
EnslaverAlias: Simpson, D.B. 1039514
EnslaverAlias: Styles, Mrs. A.M. 1039518
EnslaverAlias: Shackleford, J. 1039521
EnslaverAlias: Graves, H.S. 1039523
EnslaverAlias: Hames, S. 1039528
EnslaverAlias: Dashell, Thomas P. 1039530
EnslaverAlias: James, Mark 1039533
EnslaverAlias: Hughes, A.M. 1039534
EnslaverAlias: Villeneuve, C. 1039537
EnslaverAlias: Maben, W.P. 1039539
EnslaverAlias: Bell, Robert A. 1039540
EnslaverAlias: Harrison, D. 1039541
EnslaverAlias: Viers 1039543
EnslaverAlias: Wright, John M. 1039544
EnslaverAlias: Verstille, N.H.S. 1039546
EnslaverAlias: Cline, John 1039551
EnslaverAlias: Freeman Jr., D.C. 1039552
EnslaverAlias: Price, C.L. 1039556
EnslaverAlias: Smith, W.F. 1039557
EnslaverAlias: McPhail, Daniel 1039561
EnslaverAlias: Jones, J.R. 1039562
EnslaverAlias: Nicholson, J.P. 1039563
EnslaverAlias: Magoffin, J. W. 1039564
EnslaverAlias: Shields, B.G. 1039565
EnslaverAlias: Booth, R.C. 1039567
EnslaverAlias: Hatchett, N.P. 1039569
EnslaverAlias: McKassack, Y. W. H. 1039571
EnslaverAlias: Winn, Baylor 1039572
EnslaverAlias: Martin, J.E. 1039573
EnslaverAlias: Ware, James 1039574
EnslaverAlias: Holman, J.S. 1039576
EnslaverAlias: Isbell, J.C. 1039578
EnslaverAlias: Dorsey, Orlando 1039580
EnslaverAlias: Wrighly, J. 1039581
EnslaverAlias: Whitt, Thomas P. 1039585
EnslaverAlias: Perkins, S.J. 1039586
EnslaverAlias: Williams, George 1039588
EnslaverAlias: Putney, R.J. 1039590
EnslaverAlias: Walker, J.C. 1039592
EnslaverAlias: Carez, W.G. 1039593
EnslaverAlias: Shaw, P. A. 1039596
EnslaverAlias: Smith, D.C. 1039600
EnslaverAlias: Johnston, James 1039601
EnslaverAlias: McFadden, E.A. 1039604
EnslaverAlias: Cassino, Jose 1039606
EnslaverAlias: Burton, C.W. 1039610
EnslaverAlias: Slaughter, W.S. 1039612
EnslaverAlias: Tillman, F. 1039613
EnslaverAlias: Nichols, E.B. 1039617
EnslaverAlias: Thrash, David E. 1039618
EnslaverAlias: Easley, Sam A. 1039621
EnslaverAlias: Ransom, R.N. 1039627
EnslaverAlias: Cheatham, J.A. 1039630
EnslaverAlias: Hamblen, William 1039631
EnslaverAlias: Wood, Green 1039632
EnslaverAlias: Garner, Thomas 1039634
EnslaverAlias: Erickson, F. 1039635
EnslaverAlias: Toutant, A. 1039638
EnslaverAlias: Brooke, John C. 1039640
EnslaverAlias: Morgan, D.A. 1039643
EnslaverAlias: Elmar, Henry M. 1039644
EnslaverAlias: Perry, W.H.C. 1039645
EnslaverAlias: Slaughter, A.B. 1039646
EnslaverAlias: Schley, George H. 1039647
EnslaverAlias: Galbraith, E.D. 1039650
EnslaverAlias: Sharp, W.H. 1039656
EnslaverAlias: McNeal, S.L. 1039657
EnslaverAlias: Coleman, N.P. 1039658
EnslaverAlias: Holmes, T. H. 1039659
EnslaverAlias: Battle, O.L 1039661
EnslaverAlias: Cade, James C. 1039662
EnslaverAlias: McNiell, A. 1039664
EnslaverAlias: Barton, Hugh 1039665
EnslaverAlias: Fox, John A. 1039668
EnslaverAlias: Hutchinson, W. 1039669
EnslaverAlias: Lee, Joseph K. 1039670
EnslaverAlias: Huff, Charles 1039673
EnslaverAlias: Picton, A.F. 1039674
EnslaverAlias: Cram, John R. 1039675
EnslaverAlias: Weisiger, W. 1039677
EnslaverAlias: Dennis, G.E. 1039678
EnslaverAlias: Coleman, Israel 1039680
EnslaverAlias: Cook, John F. 1039681
EnslaverAlias: Daniels, Williamson 1039683
EnslaverAlias: Porter, A. D. 1039684
EnslaverAlias: Jones, Churchill 1039685
EnslaverAlias: Stewart, C.A. 1039686
EnslaverAlias: Smith, George A. 1039687
EnslaverAlias: Carrington, W.T. 1039689
EnslaverAlias: Lee, Abraham 1039692
EnslaverAlias: Darden, Stephen H. 1039694
EnslaverAlias: Frost, Edmund 1039695
EnslaverAlias: Ware, R.C. 1039697
EnslaverAlias: Glass, H. 1039699
EnslaverAlias: Gillmore, J. 1039700
EnslaverAlias: Hughes, O'Brien S. 1039703
EnslaverAlias: McBrayn, Z.P. 1039704
EnslaverAlias: Henry, H.W. 1039705
EnslaverAlias: Broomfield, Jn 1039706
EnslaverAlias: Millbanks, R.W. 1039710
EnslaverAlias: Fisher, C.G. 1039712
EnslaverAlias: Killingsworth, H. 1039714
EnslaverAlias: Southerland, G.Q. 1039715
EnslaverAlias: Gonzales, F. 1039716
EnslaverAlias: Snapp, Lewis 1039717
EnslaverAlias: Baker, Mrs. A.S. 1039718
EnslaverAlias: Herron, A. 1039719
EnslaverAlias: Richardson, John B. 1039724
EnslaverAlias: Holt Jr., John S. 1039725
EnslaverAlias: Emerson, William 1039727
EnslaverAlias: Boyle, Francis A. 1039728
EnslaverAlias: Hooper, L.K. 1039730
EnslaverAlias: Green, J. R. 1039733
EnslaverAlias: Darden, Stephen H. 1039736
EnslaverAlias: Oliver, A.J. 1039738
EnslaverAlias: Shell, P. J. 1039740
EnslaverAlias: Clarke, J.W. 1039743
EnslaverAlias: Brown, Mrs. 1039745
EnslaverAlias: Irvin, Daniel 1039746
EnslaverAlias: Wood, A.H. 1039748
EnslaverAlias: Hendon, Joseph E. 1039749
EnslaverAlias: Stoppelberg, Louis Von 1039750
EnslaverAlias: Wright, L.B. 1039754
EnslaverAlias: Benoist, William 1039755
EnslaverAlias: Howette, F.C. 1039757
EnslaverAlias: Woods, A. 1039760
EnslaverAlias: Green, William 1039762
EnslaverAlias: Manly, John H. 1039763
EnslaverAlias: Blair, Jno. J. 1039769
EnslaverAlias: Shan, Joseph P. 1039770
EnslaverAlias: Lum, William 1039771
EnslaverAlias: Long, John S. 1039773
EnslaverAlias: Ohler, Edward 1039775
EnslaverAlias: Johnson, Joseph F. 1039778
EnslaverAlias: Baker, William 1039779
EnslaverAlias: Grimes, W. B. 1039783
EnslaverAlias: Grimes, William B. 1039787
EnslaverAlias: Andrews, R.C. 1039788
EnslaverAlias: Smith, H.G. 1039789
EnslaverAlias: Farish, Robert T. 1039790
EnslaverAlias: Hatcher, R.J. 1039791
EnslaverAlias: Baylor, G. W. 1039792
EnslaverAlias: Clark, William 1039793
EnslaverAlias: Fentress, D. W. 1039794
EnslaverAlias: Beckham, L.B. 1039795
EnslaverAlias: Monroe, E.P. 1039797
EnslaverAlias: Cummings, R.C. 1039798
EnslaverAlias: Taylor, F.M. 1039799
EnslaverAlias: Maxey, Elisha 1039800
EnslaverAlias: Sweeny, John 1039801
EnslaverAlias: Tindal, John W. 1039802
EnslaverAlias: Moon Titus & Co 1039806
EnslaverAlias: Robinson, William 1039808
EnslaverAlias: Crawford, J.W. 1039809
EnslaverAlias: Harkleread, Frank P. 1039810
EnslaverAlias: Cloman, J.W. 1039811
EnslaverAlias: Parker, William T. 1039812
EnslaverAlias: Pope, John H. 1039814
EnslaverAlias: Wilkins, Amos T. 1039815
EnslaverAlias: Johnson, William B. 1039818
EnslaverAlias: Mason, H.W. 1039819
EnslaverAlias: Wilson, W.C. 1039820
EnslaverAlias: Penick, L. T. 1039825
EnslaverAlias: Thayer, Fred N. 1039828
EnslaverAlias: Merrill, Henry 1039829
EnslaverAlias: Kirby, E. O. 1039830
EnslaverAlias: Blair, John J. 1039831
EnslaverAlias: Harvey, R.B. 1039832
EnslaverAlias: Smith, Henry G. 1039834
EnslaverAlias: Clay, Green 1039835
EnslaverAlias: Cleveland, John S. 1039837
EnslaverAlias: Cottingham, Charles 1039840
EnslaverAlias: Creigh, Charles S. 1039842
EnslaverAlias: Gayle, Charles M.S. 1039843
EnslaverAlias: Spier, Willis 1039845
EnslaverAlias: Hinkle, S. 1039846
EnslaverAlias: Grisham, Thomas S. 1039848
EnslaverAlias: Shriver, Daniel M. 1039851
EnslaverAlias: Brown, Louis H. 1039854
EnslaverAlias: Austin, Andrew 1039855
EnslaverAlias: Bedwell, W.D. 1039856
EnslaverAlias: Flewellen, R.F. 1039857
EnslaverAlias: Grissett, John D. 1039858
EnslaverAlias: Potts, Frank M. 1039860
EnslaverAlias: Faulkner, A.C. 1039861
EnslaverAlias: McNeel, Sterling 1039864
EnslaverAlias: Connie, J.R. 1039869
EnslaverAlias: Greenwood, T. B. 1039871
EnslaverAlias: Smith, G. 1039872
EnslaverAlias: Spiller, T.H. 1039876
EnslaverAlias: Hillyard, James 1039880
EnslaverAlias: Tate, Waddy 1039881
EnslaverAlias: McIntyre, R.T. 1039883
EnslaverAlias: Evans, William 1039885
EnslaverAlias: Amslee, Charles 1039887
EnslaverAlias: Holman, H.C. 1039888
EnslaverAlias: Logue, John G. 1039889
EnslaverAlias: Morrison, Wesley 1039892
EnslaverAlias: Wilkins, M.M. 1039894
EnslaverAlias: Shelly, John 1039895
EnslaverAlias: FitzPatrick, David 1039896
EnslaverAlias: Knox, J.D. 1039897
EnslaverAlias: Bates, J.R. 1039898
EnslaverAlias: McLeeney, John F. 1039899
EnslaverAlias: Wright, J.W.P. 1039901
EnslaverAlias: Sessions, H. W. 1039902
EnslaverAlias: Kenzie, A.M. 1039905
EnslaverAlias: Sandford, John R. 1039908
EnslaverAlias: Edmonson, William A. 1039910
EnslaverAlias: Huff, L.C. 1039913
EnslaverAlias: Hawkins, John D. 1039917
EnslaverAlias: Jones, John H. 1039918
EnslaverAlias: Allston, P. J. 1039919
EnslaverAlias: Hamilton, Gen. J. 1039920
EnslaverAlias: Smith, P.D. 1039924
EnslaverAlias: Windrow, C. 1039925
EnslaverAlias: Patten, G.L. 1039927
EnslaverAlias: Hablum, E.M. 1039929
EnslaverAlias: Bowen, C.W. 1039930
EnslaverAlias: Baker, Morel 1039932
EnslaverAlias: Price, J.H. 1039934
EnslaverAlias: Hefford, Louisa 1039936
EnslaverAlias: Boyle, F.A. 1039938
EnslaverAlias: Duggins, F.P. 1039940
EnslaverAlias: Wilkins, Iasiah 1039942
EnslaverAlias: Freeman, William G. 1039943
EnslaverAlias: Waul, T.M. 1039944
EnslaverAlias: Hodges, John 1039948
EnslaverAlias: Taylor, L.B. 1039949
EnslaverAlias: McCloy, Alex 1039952
EnslaverAlias: McLeod, James 1039955
EnslaverAlias: Donaldson, A.H. 1039961
EnslaverAlias: Watson, Joseph 1039962
EnslaverAlias: Rockwood, George T. 1039965
EnslaverAlias: Hooks, F.H. 1039967
EnslaverAlias: Callaway, Alford 1039968
EnslaverAlias: Bryan, Louis A. 1039970
EnslaverAlias: Sorrel, R.H. 1039972
EnslaverAlias: Bohannon, R.E. 1039973
EnslaverAlias: Seton, G.S. 1039975
EnslaverAlias: Smith, John 1039978
EnslaverAlias: Cockburn, William 1039979
EnslaverAlias: Price, J.M. 1039980
EnslaverAlias: Phelps, O.C. 1039981
EnslaverAlias: Pye, J.B. 1039984
EnslaverAlias: Lockart, R. & Co 1039985
EnslaverAlias: Goodlett, W.C. 1039988
EnslaverAlias: Dearmond, William P. 1039990
EnslaverAlias: Stevens, W.A. 1039992
EnslaverAlias: Goodwin, Thomas T. 1039995
EnslaverAlias: Layton, R.A. 1039996
EnslaverAlias: Buster, S.M. 1040001
EnslaverAlias: Lynn, Lewis 1040003
EnslaverAlias: Lockhart, William 1040005
EnslaverAlias: Gerry, B.H. 1040008
EnslaverAlias: Mather, Thad 1040010
EnslaverAlias: Cooke, F.H. 1040012
EnslaverAlias: Hatcher, J.T. 1040014
EnslaverAlias: Dunovant & Gordon 1040015
EnslaverAlias: Boozman, J.W. 1040017
EnslaverAlias: Evans, W. 1040019
EnslaverAlias: Colton, D.E. 1040021
EnslaverAlias: Dowdy, Dan O. 1040022
EnslaverAlias: Wade, William 1040023
EnslaverAlias: Jones, Thomas B. 1040025
EnslaverAlias: Thompson, A.J. 1040027
EnslaverAlias: de Gaston, Charles 1040032
EnslaverAlias: Harrell, F.M. 1040033
EnslaverAlias: Elmore, William A. 1040034
EnslaverAlias: Motley, Samuel J. 1040037
EnslaverAlias: Passmore, B.A. 1040040
EnslaverAlias: Hensley, W.R. 1040041
EnslaverAlias: McDow, Arthur 1040043
EnslaverAlias: Stubbs, William A. 1040045
EnslaverAlias: Mallett, William S. 1040048
EnslaverAlias: Dennison, G.S. 1040049
EnslaverAlias: Cail, Richard 1040050
EnslaverAlias: Chambers, William 1040051
EnslaverAlias: Robbins, John 1040054
EnslaverAlias: Speed, Thomas 1040056
EnslaverAlias: Post, W.G. 1040057
EnslaverAlias: Robinson, James 1040059
EnslaverAlias: Bernard, J.E. 1040060
EnslaverAlias: Wyatt, T.S. 1040061
EnslaverAlias: Chivers, A. S. 1040063
EnslaverAlias: Lindsey, M.W. 1040064
EnslaverAlias: Cleveland, A.D. 1040068
EnslaverAlias: Steele, G.G. 1040069
EnslaverAlias: York, J. 1040072
EnslaverAlias: Harkey, John 1040073
EnslaverAlias: Greenwood, T.C. 1040075
EnslaverAlias: Cotton, H.L. 1040076
EnslaverAlias: Huskey, B. 1040077
EnslaverAlias: Harrison, W. 1040078
EnslaverAlias: Whilden, John T. 1040079
EnslaverAlias: Gibson, Henry 1040082
EnslaverAlias: Paine, John C. 1040083
EnslaverAlias: Johnson, A.J. 1040084
EnslaverAlias: Norris, William 1040085
EnslaverAlias: Brown, H. W. 1040086
EnslaverAlias: Heard, J.H. 1040087
EnslaverAlias: Harrison, Thomas 1040088
EnslaverAlias: Goodwin, John 1040089
EnslaverAlias: Atkins, B. F. 1040091
EnslaverAlias: Mitchell, J. 1040092
EnslaverAlias: Millar, W.R. 1040093
EnslaverAlias: Wright, John J. 1040098
EnslaverAlias: Smith, D.M. 1040099
EnslaverAlias: Andrews, G.W. 1040100
EnslaverAlias: Evans, W.A. 1040101
EnslaverAlias: Vogel, Philipp 1040102
EnslaverAlias: Bismuth, Henry S. 1040104
EnslaverAlias: Biscone, A.H. 1040109
EnslaverAlias: Wells, T. 1040111
EnslaverAlias: Clark, H. 1040113
EnslaverAlias: Jones, H. N. 1040115
EnslaverAlias: Gould, W.C. 1040116
EnslaverAlias: Sterrett, John H. 1040117
EnslaverAlias: Mills, William 1040118
EnslaverAlias: Harper, R. 1040120
EnslaverAlias: Emison, William 1040121
EnslaverAlias: Robinson, Thomas B. 1040123
EnslaverAlias: Browder, B.M. 1040125
EnslaverAlias: Swan, Orange 1040126
EnslaverAlias: St Clair, J.L. 1040128
EnslaverAlias: Harrison, M.H. & Bro. 1040129
EnslaverAlias: Betts, Jesse 1040133
EnslaverAlias: Daniel, J.P. 1040136
EnslaverAlias: Bailey, J.H. 1040139
EnslaverAlias: Hart, John 1040143
EnslaverAlias: Boyle, James M. 1040144
EnslaverAlias: McNair, James 1040145
EnslaverAlias: King, Jacob 1040146
EnslaverAlias: Collin, John 1040147
EnslaverAlias: Rawls, J. C. 1040148
EnslaverAlias: Bower, G. 1040149
EnslaverAlias: Rose, Patrick 1040150
EnslaverAlias: Mooney, John 1040155
EnslaverAlias: Puryear, Wesley 1040156
EnslaverAlias: Homan, J.W. 1040157
EnslaverAlias: Turner, M.G. 1040158
EnslaverAlias: Cody, A.J. 1040159
EnslaverAlias: Lane, Edwin J. 1040161
EnslaverAlias: Barnes, J.S. 1040162
EnslaverAlias: Morrill, D. W. 1040165
EnslaverAlias: Walker, T.V. 1040166
EnslaverAlias: Baker, A. 1040168
EnslaverAlias: McDonnell, T. 1040169
EnslaverAlias: Johnson, Jgs S. 1040171
EnslaverAlias: Birdwell, J.N. 1040172
EnslaverAlias: Lockett, Henry C. 1040173
EnslaverAlias: Mays, William D. 1040174
EnslaverAlias: Kimhough, C.L. 1040175
EnslaverAlias: Winston, A. 1040176
EnslaverAlias: Callot, M. 1040178
EnslaverAlias: Lewis, C.C. 1040179
EnslaverAlias: Chambers, U.B. 1040181
EnslaverAlias: Fullerton, John 1040183
EnslaverAlias: Vaughan, H.C. 1040184
EnslaverAlias: Mathews,J. J. 1040186
EnslaverAlias: Townsend, W.P. 1040187
EnslaverAlias: Chambers, B.J. 1040190
EnslaverAlias: Morgan, J.B. 1040193
EnslaverAlias: Thomas, L. 1040196
EnslaverAlias: Grymes, A.T. 1040200
EnslaverAlias: Ayres, Eli L. 1040202
EnslaverAlias: Hardee, Robert, H. 1040204
EnslaverAlias: Baldwin, John 1040205
EnslaverAlias: Shaver, B. 1040206
EnslaverAlias: Emory, James 1040209
EnslaverAlias: Penick, J. 1040212
EnslaverAlias: Womble, N.C. 1040213
EnslaverAlias: Kindrer, J.E. 1040214
EnslaverAlias: Young, H.W. 1040216
EnslaverAlias: White, James 1040218
EnslaverAlias: Dance, James W. 1040219
EnslaverAlias: Bennett, W. 1040220
EnslaverAlias: Wheeler, Daniel C. 1040221
EnslaverAlias: Shepard, James E. 1040223
EnslaverAlias: Wright, John 1040224
EnslaverAlias: Rutherford, R.W. 1040225
EnslaverAlias: Dibrell, C.C. 1040226
EnslaverAlias: Clayborn, D. D. 1040228
EnslaverAlias: Beaumont, F. 1040229
EnslaverAlias: Townsend, G.W. 1040230
EnslaverAlias: Farragut, W. 1040233
EnslaverAlias: Sintjon, H.C. 1040235
EnslaverAlias: Chambly, N. 1040238
EnslaverAlias: Wood, L.D.C 1040240
EnslaverAlias: Mason, J.W. 1040241
EnslaverAlias: Humphreys, P.W. 1040247
EnslaverAlias: Wright, James 1040251
EnslaverAlias: Middleton, J. 1040253
EnslaverAlias: Beal, W.M. 1040254
EnslaverAlias: Dumas, J. Edward 1040255
EnslaverAlias: Gaston, R.H. 1040256
EnslaverAlias: Tourant, A. 1040257
EnslaverAlias: Adkins, W. 1040259
EnslaverAlias: Bergeron, Jules 1040262
EnslaverAlias: Kalteyer, F. 1040264
EnslaverAlias: Crosland, D.E. 1040265
EnslaverAlias: Croom, J.H. 1040266
EnslaverAlias: Jones, Henry B. 1040268
EnslaverAlias: Lacky, J.J. 1040275
EnslaverAlias: Keeland, Sam E. 1040276
EnslaverAlias: Cardwell, J.W. 1040277
EnslaverAlias: Andrews, J.H. 1040278
EnslaverAlias: Macmurdo, R.L. 1040279
EnslaverAlias: Kingston, Samuel M. 1040280
EnslaverAlias: Hamilton, James 1040282
EnslaverAlias: Settle, John A. 1040284
EnslaverAlias: Ferguson, David 1040285
EnslaverAlias: Norton, J.T. 1040287
EnslaverAlias: Mosely, L.C. 1040288
EnslaverAlias: Marsh and Ranlett 1040289
EnslaverAlias: Harrell, J. 1040291
EnslaverAlias: Nolan, W. 1040292
EnslaverAlias: Bergeon, J.A. 1040294
EnslaverAlias: Boner, R.W. 1040296
EnslaverAlias: Baldridge, A.B. 1040297
EnslaverAlias: McLean, Neil 1040300
EnslaverAlias: Lawson, James 1040301
EnslaverAlias: Chapman, J.H.H. 1040302
EnslaverAlias: Peters, B.F. 1040304
EnslaverAlias: Cone, H. H. 1040307
EnslaverAlias: Pomet, G.G. 1040309
EnslaverAlias: Ware, James A. 1040311
EnslaverAlias: Wyser, G.A. 1040312
EnslaverAlias: Carr, John F. 1040313
EnslaverAlias: Dossat, R. 1040314
EnslaverAlias: Fremont, D. 1040315
EnslaverAlias: Tucker, Leonard T. 1040316
EnslaverAlias: Modesett, John W 1040320
EnslaverAlias: Layton, Robert 1040322
EnslaverAlias: Pruit, Reuben 1040325
EnslaverAlias: Long, R.W. 1040327
EnslaverAlias: Trigg, A. 1040329
EnslaverAlias: Chambers, D.M. 1040330
EnslaverAlias: Clark, Dan C. 1040331
EnslaverAlias: Hill, R.J. 1040332
EnslaverAlias: Byrd, Benjamin 1040333
EnslaverAlias: Rippitoe, A.H. 1040334
EnslaverAlias: Jones, John L. 1040335
EnslaverAlias: Meekin, Jam 1040336
EnslaverAlias: Montgomery, John T. 1040337
EnslaverAlias: Chilton, Maj R. H. 1040338
EnslaverAlias: Wyatt, J.D. 1040341
EnslaverAlias: Smith, N.S. 1040342
EnslaverAlias: Bryan, Lewis 1040345
EnslaverAlias: Estes, T.S. 1040347
EnslaverAlias: McCall, M.S. 1040349
EnslaverAlias: Thompson, Charles 1040350
EnslaverAlias: Myer, Thomas 1040352
EnslaverAlias: Hanna, James S. 1040354
EnslaverAlias: Warfield, E. 1040355
EnslaverAlias: Aldridge, Joseph 1040357
EnslaverAlias: Walker, J.G. 1040358
EnslaverAlias: Hagerty, Jas. M. 1040359
EnslaverAlias: Gray, H.C. 1040363
EnslaverAlias: Egan, Mrs. B. 1040365
EnslaverAlias: Scurlock, William 1040366
EnslaverAlias: Henry, John S. 1040367
EnslaverAlias: Breaken, William H. 1040368
EnslaverAlias: Threadgill, John 1040370
EnslaverAlias: Snodgrass, H. 1040371
EnslaverAlias: Garrett, S. 1040374
EnslaverAlias: Farris, G.W. 1040375
EnslaverAlias: Mitchell, J.A. 1040376
EnslaverAlias: Ingram, B. T. 1040379
EnslaverAlias: Cross, John S. 1040380
EnslaverAlias: Russell, L.H. 1040381
EnslaverAlias: Austin, Edward T. 1040383
EnslaverAlias: Allen, R. 1040384
EnslaverAlias: Jenkins, Albert P. 1040385
EnslaverAlias: Baker, W.R. 1040386
EnslaverAlias: Green, J.F. 1040387
EnslaverAlias: Stubbs, T.B. 1040388
EnslaverAlias: Walker, James 1040389
EnslaverAlias: Hill, Thomas B. 1040390
EnslaverAlias: Axson, A.F. 1040391
EnslaverAlias: Lewis, S.K. 1040393
EnslaverAlias: Pecrick, J. 1040394
EnslaverAlias: Eggleston, J. P. 1040395
EnslaverAlias: Ingram, Washington 1040396
EnslaverAlias: Rugeley Blair Co. 1040398
EnslaverAlias: Rawles, J. C. 1040401
EnslaverAlias: North, Elisha 1040402
EnslaverAlias: Martin, J.G. 1040403
EnslaverAlias: Galbraith, E. D. 1040405
EnslaverAlias: Sands, S.R.B. 1040406
EnslaverAlias: Simonton, J.C. 1040408
EnslaverAlias: Camp, J. M. 1040409
EnslaverAlias: Cassinio, Joseph 1040410
EnslaverAlias: McKenney, John F. 1040411
EnslaverAlias: Waugh, W.H. 1040412
EnslaverAlias: Brown, J.B. 1040413
EnslaverAlias: Green, A. 1040414
EnslaverAlias: Abat, E. 1040415
EnslaverAlias: Matthews, John 1040416
EnslaverAlias: Hopkins, M. 1040417
EnslaverAlias: Buchanan, A.H. 1040418
EnslaverAlias: Lewis, G. W. 1040419
EnslaverAlias: Morgan, G. 1040420
EnslaverAlias: Hunt, William 1040421
EnslaverAlias: Lytle, William 1040423
EnslaverAlias: Buddy, George W. 1040428
EnslaverAlias: Fellows and Co. 1040429
EnslaverAlias: Black, H.W. 1040436
EnslaverAlias: Rhett, Capt. T.G. 1040438
EnslaverAlias: Wood, F.F. 1040440
EnslaverAlias: Blantley, Rugeley 1040442
EnslaverAlias: Graham, W.S. 1040443
EnslaverAlias: Lamar, Mirabeau B. 1040447
EnslaverAlias: Moore, Eunoch 1040451
EnslaverAlias: Stevens, W.W. 1040452
EnslaverAlias: Franklin, James 1040458
EnslaverAlias: Whitney, B.A. 1040459
EnslaverAlias: Gordon, John W. 1040460
EnslaverAlias: Leaverton, James H. 1040461
EnslaverAlias: Croon, J.H. 1040462
EnslaverAlias: Willie, A.H. 1040463
EnslaverAlias: Winston, Anthony 1040464
EnslaverAlias: Gibson, John A. 1040465
EnslaverAlias: Moore, Levi 1040467
EnslaverAlias: Means, William 1040469
EnslaverAlias: Crook, William 1040471
EnslaverAlias: Shannon, W.T. 1040472
EnslaverAlias: Wilkins, B.B. 1040473
EnslaverAlias: Pace, George L. 1040474
EnslaverAlias: Barrow, W.L. 1040476
EnslaverAlias: Kerr, T.A. 1040477
EnslaverAlias: Echols, John 1040478
EnslaverAlias: Hudson, S. 1040480
EnslaverAlias: Campbell, W.L. 1040482
EnslaverAlias: Leak, Robert 1040486
EnslaverAlias: Parker, Levi 1040492
EnslaverAlias: Harris, R.A. 1040494
EnslaverAlias: Gibson, William B. 1040496
EnslaverAlias: Lynch, J.B. 1040497
EnslaverAlias: Conichie, Alex M. 1040498
EnslaverAlias: Harris, J. Gauvin 1040499
EnslaverAlias: West, John W.S. 1040501
EnslaverAlias: Allsbury, H.R. 1040505
EnslaverAlias: Maxwell, D. 1040506
EnslaverAlias: Manley, John H. 1040510
EnslaverAlias: Walker, William 1040511
EnslaverAlias: Gee, William F. 1040512
EnslaverAlias: Burditt, Wm. B. 1040513
EnslaverAlias: Womack, Abner 1040514
EnslaverAlias: Belknap, J.T. 1040515
EnslaverAlias: Stamps, John 1040516
EnslaverAlias: Sterrett, John H. 1040518
EnslaverAlias: Josey, Theophilus 1040522
EnslaverAlias: Barton, James F. 1040524
EnslaverAlias: Shiner, P. 1040526
EnslaverAlias: Poindexter, J.J. 1040528
EnslaverAlias: Shannon, Timothy 1040529
EnslaverAlias: Robertson, F.W. 1040530
EnslaverAlias: Wagner, J.H. 1040532
EnslaverAlias: Tate, Riley 1040533
EnslaverAlias: Worten, P.B. 1040534
EnslaverAlias: Van Hork, M.A. 1040537
EnslaverAlias: Deains, E. 1040540
EnslaverAlias: Brewer, Wm 1040542
EnslaverAlias: White, J.R. 1040543
EnslaverAlias: Lee, Thomas B. 1040545
EnslaverAlias: Howarton, Philip 1040546
EnslaverAlias: Creite, Samuel E. 1040548
EnslaverAlias: Liddell, Andrew 1040552
EnslaverAlias: Jack, William H. 1040553
EnslaverAlias: Campbell, David A. 1040555
EnslaverAlias: Tait, James G. 1040560
EnslaverAlias: McMassengale, J.A. 1040562
EnslaverAlias: Kendall, R.B. 1040564
EnslaverAlias: Park, C.D. 1040565
EnslaverAlias: Reavis, J.G. 1040568
EnslaverAlias: Harney, W.S. 1040570
EnslaverAlias: Cleveland, W. 1040575
EnslaverAlias: Flemming, P. R. 1040576
EnslaverAlias: Lang, Willis L. 1040577
EnslaverAlias: Anderson, Z.M. 1040579
EnslaverAlias: Stafford, W.J. 1040582
EnslaverAlias: Coffee, William 1040583
EnslaverAlias: King, Jos E 1040585
EnslaverAlias: Wilson, B.F. 1040587
EnslaverAlias: Riggins, J.W. 1040588
EnslaverAlias: Gillespie, T.J. 1040589
EnslaverAlias: Vail, J. 1040590
EnslaverAlias: Keeling, John T. 1040591
EnslaverAlias: Sundy, Joshua C. 1040592
EnslaverAlias: Lane, J.W. 1040594
EnslaverAlias: Williams, James A. 1040595
EnslaverAlias: Chiles, James 1040596
EnslaverAlias: Rhodes, Henry W. 1040597
EnslaverAlias: Soutra, Joseph 1040599
EnslaverAlias: West, Nathaniel 1040600
EnslaverAlias: Williams, J.S. 1040601
EnslaverAlias: Henderson, E. L. 1040602
EnslaverAlias: Roberts, J. A. 1040603
EnslaverAlias: Newsom, J. 1040607
EnslaverAlias: Cain, William L. 1040608
EnslaverAlias: Bowie, G.J. 1040609
EnslaverAlias: Herbert, W.J. 1040610
EnslaverAlias: Holcomb, Alfred 1040614
EnslaverAlias: MacKay, John 1040615
EnslaverAlias: Bounds, John 1040617
EnslaverAlias: Cannon, L. 1040619
EnslaverAlias: Beck, R. 1040620
EnslaverAlias: Morris, J.J. 1040621
EnslaverAlias: Mayberry, D. 1040624
EnslaverAlias: Brown, J.W. 1040625
EnslaverAlias: Sims, Ferdinand 1040626
EnslaverAlias: Thomas, John 1040628
EnslaverAlias: Matthews, William P. 1040629
EnslaverAlias: McKean, Willis 1040631
EnslaverAlias: Keeton, Robert 1040633
EnslaverAlias: Gordon, J.W. 1040634
EnslaverAlias: Rhea, J. 1040635
EnslaverAlias: Boner, J. 1040636
EnslaverAlias: Dunn, B.H. 1040638
EnslaverAlias: Foster, John D. 1040639
EnslaverAlias: Moss, B.F. 1040640
EnslaverAlias: Hardison, C.B. 1040641
EnslaverAlias: Allen, W.J. heirs of 1040642
EnslaverAlias: Chandler, William H. 1040644
EnslaverAlias: Lockett, H.E. 1040645
EnslaverAlias: Wells, Daniel 1040646
EnslaverAlias: Grisset, Jno. D. 1040649
EnslaverAlias: Haviland, J.E. 1040652
EnslaverAlias: Allen, J.D. 1040654
EnslaverAlias: Hastings, Green 1040655
EnslaverAlias: Byrne, P.R. 1040657
EnslaverAlias: Cowan, David C. 1040658
EnslaverAlias: Mays, William B. 1040660
EnslaverAlias: Remick, William 1040664
EnslaverAlias: Saunders, Philip 1040668
EnslaverAlias: Smith, Ash. 1040670
EnslaverAlias: Kirbey, Mrs. 1040676
EnslaverAlias: Lumsden, A.M. 1040680
EnslaverAlias: Biggep, Samuel 1040683
EnslaverAlias: Jackson, G. 1040687
EnslaverAlias: Bonner, William 1040688
EnslaverAlias: Brown, W.H. 1040689
EnslaverAlias: Whitby, William 1040690
EnslaverAlias: Tate, Maddy 1040691
EnslaverAlias: Holt, John S. 1040693
EnslaverAlias: Teal, John T. 1040695
EnslaverAlias: Arnold, R. A. 1040696
EnslaverAlias: Rhoades, John 1040698
EnslaverAlias: Boyd, G. H. 1040699
EnslaverAlias: Gillespie, C.C. 1040701
EnslaverAlias: Hill, William G. 1040702
EnslaverAlias: Zink, Nicolas 1040703
EnslaverAlias: Barnes, William 1040705
EnslaverAlias: Spears, Nathan I. 1040707
EnslaverAlias: Miller, G.W. 1040711
EnslaverAlias: Whelsett, R.G. 1040712
EnslaverAlias: Quartes, D.W. 1040715
EnslaverAlias: Tongue, G.G. 1040717
EnslaverAlias: McLin, J. D. 1040719
EnslaverAlias: Meriwether, William H. 1040720
EnslaverAlias: Jinn, John F. 1040721
EnslaverAlias: Hawkins, J.D. 1040723
EnslaverAlias: Sample, J. 1040724
EnslaverAlias: Foster, A. 1040725
EnslaverAlias: Hood, Thomas 1040726
EnslaverAlias: Christy, William & Son 1040727
EnslaverAlias: May, A.A. 1040728
EnslaverAlias: Cram, John R. 1040731
EnslaverAlias: Weyser, G.A. 1040733
EnslaverAlias: Bryant, Owen 1040737
EnslaverAlias: Lucas, B. L. 1040738
EnslaverAlias: Harden, F.J. 1040741
EnslaverAlias: Mapp, H.H. 1040742
EnslaverAlias: McCarty, M. 1040743
EnslaverAlias: Bardin, Warden 1040744
EnslaverAlias: Felder, E.J. 1040746
EnslaverAlias: McFairbain, J.N. 1040747
EnslaverAlias: Anderson, William 1040748
EnslaverAlias: Everitt, E. 1040750
EnslaverAlias: Norwood, Peter 1040752
EnslaverAlias: Breedlove, James W. 1040754
EnslaverAlias: Landrum, Sam 1040755
EnslaverAlias: Blakey, R.S. 1040757
EnslaverAlias: Bigot, T. F. 1040758
EnslaverAlias: Sims, M.W. 1040760
EnslaverAlias: Gribble, R.D. 1040763
EnslaverAlias: Burrow, E. 1040764
EnslaverAlias: Rutherford, F. A. 1040765
EnslaverAlias: Evens, John 1040770
EnslaverAlias: Scott, O. 1040771
EnslaverAlias: Brevard, E.J. 1040772
EnslaverAlias: Quinney, Lafayette 1040781
EnslaverAlias: Rugdey, Alex 1040782
EnslaverAlias: Cronkrite, L. 1040783
EnslaverAlias: Burton, F. B. 1040784
EnslaverAlias: Lee, William 1040786
EnslaverAlias: Smith, Thomas 1040788
EnslaverAlias: Chirouze, L. 1040789
EnslaverAlias: Lindsay, John B. 1040791
EnslaverAlias: Lindsey, D. 1040792
EnslaverAlias: Cannon, Henry 1040799
EnslaverAlias: Brown, W.W. 1040803
EnslaverAlias: Taylor, James 1040804
EnslaverAlias: Sorsly, W.C. 1040805
EnslaverAlias: Perkins, C. 1040808
EnslaverAlias: Scooffy, P.M. 1040810
EnslaverAlias: Fierson, G.B. 1040812
EnslaverAlias: Hawthorne, Bogert 1040816
EnslaverAlias: Allen, R.L. 1040819
EnslaverAlias: Young, George W. 1040820
EnslaverAlias: Carter, Edward R. 1040826
EnslaverAlias: McGill, Daniel 1040827
EnslaverAlias: Little, George A. 1040828
EnslaverAlias: Peebles, Dr. R. 1040829
EnslaverAlias: Donald, D.M. 1040836
EnslaverAlias: Smith, C.W. 1040837
EnslaverAlias: Vincent, Flerwell 1040839
EnslaverAlias: Mitchell, Robert F. 1040841
EnslaverAlias: Blair, J.D. 1040842
EnslaverAlias: Manlove, B. 1040844
EnslaverAlias: Graves, G.W. 1040847
EnslaverAlias: Hefford, L.T. 1040848
EnslaverAlias: Venable, William G. 1040849
EnslaverAlias: Rhodes, William R. 1040852
EnslaverAlias: Cosnahan, J.B. 1040854
EnslaverAlias: Clarke, William J. 1040855
EnslaverAlias: Offutt, H.J. 1040857
EnslaverAlias: Foster, J.M. 1040858
EnslaverAlias: Jenkins, John 1040859
EnslaverAlias: Walton, William 1040860
EnslaverAlias: Edgeworth, A.E. 1040862
EnslaverAlias: Wilson, L. M. 1040864
EnslaverAlias: Owen, Tom M. 1040865
EnslaverAlias: Higgs, W. 1040866
EnslaverAlias: West, J. C. 1040868
EnslaverAlias: Rugeley, A.J. 1040869
EnslaverAlias: Terry, Williamson 1040871
EnslaverAlias: Polk, Louis 1040873
EnslaverAlias: Ashby, James 1040875
EnslaverAlias: White, William 1040876
EnslaverAlias: Zunts, M. 1040880
EnslaverAlias: Wilder, J.T. 1040881
EnslaverAlias: Taylor, Thomas L. 1040882
EnslaverAlias: Clements, Thomas B. 1040885
EnslaverAlias: Baldwin, J.J. 1040887
EnslaverAlias: Simmons, Noah 1040888
EnslaverAlias: Thorp, Joseph B. 1040889
EnslaverAlias: Jones, James S. 1040890
EnslaverAlias: Adams, Jra. A. 1040891
EnslaverAlias: Blake, Thomas C. 1040894
EnslaverAlias: McGinnis, H.P. 1040896
EnslaverAlias: Wright, Abraham 1040900
EnslaverAlias: Daniel, E. 1040901
EnslaverAlias: Wiggins, William H. 1040902
EnslaverAlias: Callaway, A.C. 1040903
EnslaverAlias: Lepscomb, Y.G. 1040904
EnslaverAlias: Drisdale, John 1040905
EnslaverAlias: Creary, J.B. 1040908
EnslaverAlias: Rutherford, R.A. 1040910
EnslaverAlias: Haviland J.E. 1040913
EnslaverAlias: Smithson, William T.M. 1040918
EnslaverAlias: Rhea, John S. 1040919
EnslaverAlias: Hagan, H. 1040922
EnslaverAlias: Montgomery, G. 1040923
EnslaverAlias: Bledroe, T.L. 1040924
EnslaverAlias: Hicks, W. 1040925
EnslaverAlias: Woodward, Elbert 1040926
EnslaverAlias: Herbert, P. Walter 1040928
EnslaverAlias: Beverley, H.M. 1040930
EnslaverAlias: Andrews, John S. 1040931
EnslaverAlias: Morse, A. 1040937
EnslaverAlias: Fry, Major C.H. 1040942
EnslaverAlias: Calloway, Milton M. 1040945
EnslaverAlias: Rall, Ruben 1040948
EnslaverAlias: Young, George 1040949
EnslaverAlias: Bradley, Wilson & Co. 1040950
EnslaverAlias: Harper, E.A. 1040952
EnslaverAlias: Holt, John 1040954
EnslaverAlias: Bendixen, L.A. 1040956
EnslaverAlias: Grave, R.L. 1040958
EnslaverAlias: Davidson, A.H. 1040959
EnslaverAlias: Ruthford, Mary 1040964
EnslaverAlias: McDonald, A. 1040966
EnslaverAlias: Robinson, Tod 1040967
EnslaverAlias: Barnes, Jno. T. 1040970
EnslaverAlias: Points, G.W. 1040971
EnslaverAlias: Moncruff 1040972
EnslaverAlias: Reid, John R. 1040974
EnslaverAlias: Mann, J.C. 1040975
EnslaverAlias: Winston, E.E. 1040979
EnslaverAlias: Walton, J.W.E. 1040980
EnslaverAlias: Garey, John E. 1040981
EnslaverAlias: Banks, Robert B. 1040982
EnslaverAlias: Doitgh, D. 1040983
EnslaverAlias: Allen, Robert D. 1040988
EnslaverAlias: Wells, W.F. 1040993
EnslaverAlias: Snodgrass, Robert L. 1040994
EnslaverAlias: Farmer, Jordan 1040995
EnslaverAlias: Stewart, Charles 1040996
