# Blog migration steps (the fk dance...)

First, move the data over

1. blog_institution
1. blog_author
1. blog_post
1. blog_post_authors
1. blog_tag
1. blog_post_tags


e.g., ```insert into blog_institution select * from nov_prod.blog_institution;```

# Then, map the image fields

replace ```blog/images/``` and ```blog/Nothing``` with ```static/uploads/```:


	update blog_post set thumbnail=REPLACE(thumbnail,'blog/Nothing/','static/uploads/');
	update blog_post set thumbnail=REPLACE(thumbnail,'blog/images/','static/uploads/');


then author photos

	update blog_author set photo=REPLACE(photo,'images/','static/uploads/');
	
then institutions

	update blog_institution set image=REPLACE(image,'images/','static/uploads/');

And that should do it -- you'll still need to push all the prod assets from these various sources into static/uploads/ on the mount point, of course.

