ITER=-12
for page in pages/*.txt
do  
    cat $page
    echo "((page ${ITER}))"
    ITER=$(expr $ITER + 1)
done > book_with_pages.txt
